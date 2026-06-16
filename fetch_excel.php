<?php
/**
 * fetch_excel.php
 * Скачивает последний Excel-файл за каждый день за последние 2 недели
 * из IMAP-почты (без расширения php-imap, через SSL-сокет).
 *
 * Настройки: ~/ASU_PODHOD/settings.json
 * Запуск:    php fetch_excel.php
 */

define('EXCEL_EXTS', ['xlsx', 'xls', 'xlsm', 'xltx', 'xltm']);
define('OUTPUT_DIR',  __DIR__ . '/');
define('DAYS_BACK',   14);

// ═══════════════════════════════════════════════════════════════════════════════
//  IMAP-клиент на чистых сокетах (не требует php-imap)
// ═══════════════════════════════════════════════════════════════════════════════

class RawIMAP {
    private $socket = null;
    private int $tag = 0;

    public function connect(string $host, int $port, int $timeout = 30): bool {
        $ctx = stream_context_create(['ssl' => [
            'verify_peer'      => false,
            'verify_peer_name' => false,
            'allow_self_signed'=> true,
        ]]);
        $this->socket = @stream_socket_client(
            "ssl://{$host}:{$port}", $errno, $errstr, $timeout,
            STREAM_CLIENT_CONNECT, $ctx
        );
        if (!$this->socket) {
            echo "[ERROR] Соединение не установлено: {$errstr} ({$errno})\n";
            return false;
        }
        stream_set_timeout($this->socket, $timeout);
        $this->readLine(); // приветствие сервера
        return true;
    }

    public function login(string $user, string $pass): bool {
        return $this->isOK($this->cmd(
            'LOGIN ' . $this->q($user) . ' ' . $this->q($pass)
        ));
    }

    public function select(string $mailbox): bool {
        return $this->isOK($this->cmd('SELECT ' . $this->q($mailbox)));
    }

    /** Возвращает номера сообщений по критерию поиска */
    public function search(string $criteria): array {
        foreach ($this->cmd("SEARCH $criteria") as $line) {
            if (preg_match('/^\* SEARCH\s+(.+)$/i', $line, $m)) {
                return array_map('intval', preg_split('/\s+/', trim($m[1])));
            }
        }
        return [];
    }

    /** Unix-timestamp внутренней даты сообщения */
    public function internalDate(int $num): int {
        foreach ($this->cmd("FETCH {$num} INTERNALDATE") as $line) {
            if (preg_match('/INTERNALDATE\s+"([^"]+)"/i', $line, $m)) {
                return strtotime($m[1]) ?: 0;
            }
        }
        return 0;
    }

    /** Загружает полное RFC-822 сообщение */
    public function fetchRaw(int $num): string {
        $tag = $this->nextTag();
        fwrite($this->socket, "{$tag} FETCH {$num} BODY.PEEK[]\r\n");

        $body = '';
        $needBytes = -1;

        while (!feof($this->socket)) {
            if ($needBytes > 0) {
                $chunk = fread($this->socket, min($needBytes, 65536));
                if ($chunk === false) break;
                $body    .= $chunk;
                $needBytes -= strlen($chunk);
            } elseif ($needBytes === 0) {
                // дочитываем до закрывающей строки тега
                $line = $this->readLine();
                if (str_starts_with($line, $tag . ' ')) break;
            } else {
                $line = $this->readLine();
                if (preg_match('/\{(\d+)\}$/', $line, $m)) {
                    $needBytes = (int)$m[1];
                } elseif (str_starts_with($line, $tag . ' ')) {
                    break;
                }
            }
        }
        return $body;
    }

    public function logout(): void {
        if ($this->socket) {
            try { $this->cmd('LOGOUT'); } catch (\Throwable $e) {}
            fclose($this->socket);
            $this->socket = null;
        }
    }

    // ── внутренние ────────────────────────────────────────────────────────────

    private function cmd(string $command): array {
        $tag = $this->nextTag();
        fwrite($this->socket, "{$tag} {$command}\r\n");
        $lines = [];
        while (!feof($this->socket)) {
            $line    = $this->readLine();
            $lines[] = $line;
            if (str_starts_with($line, $tag . ' ')) break;
        }
        return $lines;
    }

    private function readLine(): string {
        $line = fgets($this->socket, 8192);
        return $line !== false ? rtrim($line, "\r\n") : '';
    }

    private function nextTag(): string {
        return 'T' . str_pad(++$this->tag, 5, '0', STR_PAD_LEFT);
    }

    private function isOK(array $lines): bool {
        foreach ($lines as $l) {
            if (preg_match('/^T\d{5} OK\b/i', $l)) return true;
        }
        return false;
    }

    private function q(string $s): string {
        return '"' . str_replace(['\\', '"'], ['\\\\', '\\"'], $s) . '"';
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Разбор MIME-сообщения
// ═══════════════════════════════════════════════════════════════════════════════

function mime_headers(string $raw): array {
    $headers = [];
    // Раскрываем folded headers
    $raw = preg_replace("/\r\n([ \t])/", '$1', $raw);
    $raw = preg_replace("/\n([ \t])/",   '$1', $raw);
    foreach (preg_split("/\r?\n/", $raw) as $line) {
        $pos = strpos($line, ':');
        if ($pos === false) continue;
        $key = strtolower(trim(substr($line, 0, $pos)));
        $val = trim(substr($line, $pos + 1));
        $headers[$key] = $val;
    }
    return $headers;
}

function mime_decode_word(string $encoded): string {
    // =?charset?B/Q?text?=
    return preg_replace_callback(
        '/=\?([^?]+)\?([BbQq])\?([^?]+)\?=/',
        function ($m) {
            $charset = $m[1];
            $text    = strtoupper($m[2]) === 'B'
                ? base64_decode($m[3])
                : quoted_printable_decode(str_replace('_', ' ', $m[3]));
            return mb_convert_encoding($text, 'UTF-8', $charset);
        },
        $encoded
    );
}

/**
 * Рекурсивно обходит MIME-части, возвращает список Excel-вложений:
 * [['name' => string, 'data' => string], ...]
 */
function mime_excel_attachments(string $raw): array {
    // Разделяем заголовки и тело
    foreach (["\r\n\r\n", "\n\n"] as $sep) {
        $pos = strpos($raw, $sep);
        if ($pos !== false) {
            $hdr  = substr($raw, 0, $pos);
            $body = substr($raw, $pos + strlen($sep));
            break;
        }
    }
    if (!isset($hdr)) return [];

    $headers = mime_headers($hdr);
    $ct      = $headers['content-type'] ?? 'text/plain';

    // Multipart?
    if (preg_match('/^multipart\//i', $ct)) {
        if (!preg_match('/boundary="?([^";\s]+)"?/i', $ct, $bm)) return [];
        $boundary = $bm[1];
        $results  = [];
        // Разбиваем по границе
        $parts = preg_split('/(?:\r?\n)?--' . preg_quote($boundary, '/') . '(?:--)?(?:\r\n|\n|$)/m', $body);
        foreach (array_slice($parts, 1) as $part) {  // первый элемент — преамбула
            $results = array_merge($results, mime_excel_attachments(ltrim($part, "\r\n")));
        }
        return $results;
    }

    // Одиночная часть — проверяем: это вложение?
    $disp = $headers['content-disposition'] ?? '';
    $name = '';

    // Имя из Content-Disposition
    if (preg_match('/filename\*?=(?:"([^"]+)"|([^;\s]+))/i', $disp, $nm)) {
        $name = mime_decode_word($nm[1] ?: $nm[2]);
    }
    // Имя из Content-Type (name=...)
    if (!$name && preg_match('/name="?([^";]+)"?/i', $ct, $nm)) {
        $name = mime_decode_word($nm[1]);
    }

    if (!$name) return [];

    $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
    if (!in_array($ext, EXCEL_EXTS, true)) return [];

    // Декодирование содержимого
    $encoding = strtolower($headers['content-transfer-encoding'] ?? '');
    $data     = $body;
    if ($encoding === 'base64') {
        $data = base64_decode(preg_replace('/\s+/', '', $body));
    } elseif ($encoding === 'quoted-printable') {
        $data = quoted_printable_decode($body);
    }

    return [['name' => trim($name), 'data' => $data]];
}

// ═══════════════════════════════════════════════════════════════════════════════
//  settings.json
// ═══════════════════════════════════════════════════════════════════════════════

function load_settings(): array {
    // Сначала ищем рядом со скриптом
    $local = __DIR__ . '/settings.json';
    if (file_exists($local)) {
        echo "[INFO] Настройки: $local\n";
        return json_decode(file_get_contents($local), true) ?: [];
    }
    foreach (['APPDATA', 'LOCALAPPDATA', 'HOME'] as $env) {
        $base = getenv($env);
        if (!$base) continue;
        $path = rtrim($base, '/\\') . '/ASU_PODHOD/settings.json';
        if (file_exists($path)) {
            echo "[INFO] Настройки: $path\n";
            return json_decode(file_get_contents($path), true) ?: [];
        }
    }
    echo "[WARN] settings.json не найден.\n";
    return [];
}

function get_imap_cfg(array $s, string $tab): array {
    $def = [
        'enabled' => false, 'server' => '', 'port' => 993,
        'username' => '', 'password' => '', 'mailbox' => 'INBOX',
        'sender_filter' => '', 'subject_filter' => '',
        'subject_equals' => '', 'attachment_name_contains' => '',
        'attachment_name_equals' => '',
    ];
    $key = $tab === 'approach' ? 'imap_approach' : 'imap_departure';
    return array_merge($def, $s['imap'] ?? [], $s[$key] ?? []);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Сохранение файла
// ═══════════════════════════════════════════════════════════════════════════════

function safe_name(string $n): string {
    return preg_replace('/[^\w.\-]/u', '_', $n) ?: 'file.xlsx';
}

function save_file(string $tab, string $day, string $orig_name, string $data): void {
    $dest = OUTPUT_DIR . "{$tab}_{$day}_" . safe_name($orig_name);
    if (file_exists($dest)) {
        echo "  [SKIP] Уже есть: " . basename($dest) . "\n";
        return;
    }
    file_put_contents($dest, $data);
    echo "  [OK]   " . basename($dest) . " (" . round(strlen($data)/1024) . " KB)\n";
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Загрузка из IMAP
// ═══════════════════════════════════════════════════════════════════════════════

function fetch_from_imap(array $cfg, string $tab): void {
    $server   = trim($cfg['server']   ?? '');
    $port     = (int)($cfg['port']    ?? 993);
    $username = trim($cfg['username'] ?? '');
    $password =      $cfg['password'] ?? '';
    $mailbox  = trim($cfg['mailbox']  ?? '') ?: 'INBOX';

    if (!$server || !$username || !$password) {
        echo "[SKIP] Не заполнены server/username/password.\n";
        return;
    }

    $sender_filter            = strtolower(trim($cfg['sender_filter']            ?? ''));
    $subject_filter           = strtolower(trim($cfg['subject_filter']           ?? ''));
    $subject_equals           = strtolower(trim($cfg['subject_equals']           ?? ''));
    $attachment_name_contains = strtolower(trim($cfg['attachment_name_contains'] ?? ''));
    $attachment_name_equals   = strtolower(trim($cfg['attachment_name_equals']   ?? ''));

    echo "[INFO] Подключаюсь: {$server}:{$port} / {$mailbox}\n";

    $imap = new RawIMAP();
    if (!$imap->connect($server, $port)) return;
    if (!$imap->login($username, $password)) {
        echo "[ERROR] Ошибка авторизации.\n";
        $imap->logout(); return;
    }
    if (!$imap->select($mailbox)) {
        echo "[ERROR] Не удалось открыть папку «{$mailbox}».\n";
        $imap->logout(); return;
    }

    $since = date('d-M-Y', strtotime('-' . DAYS_BACK . ' days'));
    $nums  = $imap->search("SINCE \"{$since}\"");
    echo "[INFO] Писем за " . DAYS_BACK . " дней: " . count($nums) . "\n";

    if (!$nums) { $imap->logout(); return; }

    // Группируем по дню: оставляем последнее письмо за каждый день
    $by_day = [];   // 'Y-m-d' => ['num' => int, 'ts' => int]
    foreach ($nums as $num) {
        $ts  = $imap->internalDate($num);
        $day = date('Y-m-d', $ts);
        if (!isset($by_day[$day]) || $ts > $by_day[$day]['ts']) {
            $by_day[$day] = ['num' => $num, 'ts' => $ts];
        }
    }
    ksort($by_day);
    echo "[INFO] Уникальных дней: " . count($by_day) . "\n\n";

    foreach ($by_day as $day => $info) {
        echo "  $day  ";
        $raw         = $imap->fetchRaw($info['num']);
        $attachments = mime_excel_attachments($raw);

        if (!$attachments) {
            echo "[SKIP] Нет Excel-вложения.\n";
            continue;
        }

        foreach ($attachments as $att) {
            $name  = $att['name'];
            $lower = strtolower($name);

            if ($sender_filter) {
                // Проверка отправителя уже сделана на этапе SEARCH; здесь — subject
            }
            if ($subject_equals || $subject_filter) {
                // Ищем заголовок Subject в сырых данных
                if (preg_match('/^Subject:\s*(.+)$/mi', $raw, $sm)) {
                    $subj = strtolower(mime_decode_word(trim($sm[1])));
                    if ($subject_equals && $subj !== $subject_equals)             continue;
                    if ($subject_filter && !str_contains($subj, $subject_filter)) continue;
                }
            }
            if ($attachment_name_equals   && $lower !== $attachment_name_equals)              continue;
            if ($attachment_name_contains && !str_contains($lower, $attachment_name_contains)) continue;

            save_file($tab, $day, $name, $att['data']);
            break; // одно вложение на письмо
        }
    }

    $imap->logout();
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Загрузка из локальной папки
// ═══════════════════════════════════════════════════════════════════════════════

function fetch_from_folder(string $tab): void {
    $candidates = [__DIR__ . "/$tab", dirname(__DIR__) . "/$tab"];
    $folder     = null;
    foreach ($candidates as $c) {
        if (is_dir($c)) { $folder = $c; break; }
    }
    if (!$folder) { echo "[SKIP] Папка '$tab' не найдена.\n"; return; }

    echo "[INFO] Читаю папку: $folder\n";
    $files = [];
    foreach (EXCEL_EXTS as $ext) {
        foreach (glob("$folder/*.$ext") ?: [] as $f) {
            $files[] = ['path' => $f, 'mtime' => filemtime($f)];
        }
    }
    if (!$files) { echo "[SKIP] Нет Excel-файлов.\n"; return; }

    $by_day = [];
    $cutoff = strtotime('-' . DAYS_BACK . ' days');
    foreach ($files as $f) {
        if ($f['mtime'] < $cutoff) continue;
        $day = date('Y-m-d', $f['mtime']);
        if (!isset($by_day[$day]) || $f['mtime'] > $by_day[$day]['mtime']) {
            $by_day[$day] = $f;
        }
    }
    ksort($by_day);
    echo "[INFO] Дней с файлами: " . count($by_day) . "\n\n";

    foreach ($by_day as $day => $f) {
        echo "  $day  ";
        $dest = OUTPUT_DIR . "{$tab}_{$day}_" . safe_name(basename($f['path']));
        if (file_exists($dest)) { echo "[SKIP] Уже есть: " . basename($dest) . "\n"; continue; }
        copy($f['path'], $dest);
        echo "[OK]   " . basename($dest) . "\n";
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Точка входа
// ═══════════════════════════════════════════════════════════════════════════════

echo "=== fetch_excel.php (" . DAYS_BACK . " дней) ===\n";
echo "Сохранение в: " . OUTPUT_DIR . "\n\n";

$settings = load_settings();

foreach (['approach', 'departure'] as $tab) {
    echo "━━━ $tab ━━━\n";
    $cfg = get_imap_cfg($settings, $tab);

    if (!empty($cfg['enabled'])) {
        fetch_from_imap($cfg, $tab);
    } else {
        fetch_from_folder($tab);
    }
    echo "\n";
}

echo "=== Готово ===\n";
