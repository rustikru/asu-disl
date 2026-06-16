<?php
/**
 * fetch_excel.php
 * Скачивает последний Excel-файл за каждый день за последние 2 недели
 * из IMAP-почты или из локальных папок approach/ / departure/.
 * Все файлы сохраняются в директорию, где лежит этот скрипт.
 *
 * Настройки: ~/ASU_PODHOD/settings.json
 * Запуск:    php fetch_excel.php
 */

define('EXCEL_EXTS', ['xlsx', 'xls', 'xlsm', 'xltx', 'xltm']);
define('OUTPUT_DIR',  __DIR__ . '/');
define('DAYS_BACK',   14);

// ── settings.json ─────────────────────────────────────────────────────────────

function find_settings_file(): ?string {
    foreach (['APPDATA', 'LOCALAPPDATA', 'HOME'] as $env) {
        $base = getenv($env);
        if ($base) {
            $path = rtrim($base, '/\\') . '/ASU_PODHOD/settings.json';
            if (file_exists($path)) return $path;
        }
    }
    return null;
}

function load_settings(): array {
    $path = find_settings_file();
    if (!$path) {
        echo "[WARN] settings.json не найден, используются пустые настройки.\n";
        return [];
    }
    echo "[INFO] Настройки: $path\n";
    $data = json_decode(file_get_contents($path), true);
    return is_array($data) ? $data : [];
}

function get_imap_cfg(array $settings, string $tab): array {
    $default = [
        'enabled'                  => false,
        'server'                   => '',
        'port'                     => 993,
        'username'                 => '',
        'password'                 => '',
        'mailbox'                  => 'INBOX',
        'sender_filter'            => '',
        'subject_filter'           => '',
        'subject_equals'           => '',
        'attachment_name_contains' => '',
        'attachment_name_equals'   => '',
    ];
    $legacy = $settings['imap'] ?? [];
    $key    = $tab === 'approach' ? 'imap_approach' : 'imap_departure';
    return array_merge($default, $legacy, $settings[$key] ?? []);
}

// ── Вспомогательные ───────────────────────────────────────────────────────────

function is_excel(string $name): bool {
    return in_array(strtolower(pathinfo($name, PATHINFO_EXTENSION)), EXCEL_EXTS, true);
}

function safe_filename(string $name): string {
    return preg_replace('/[^\w.\-]/u', '_', $name) ?: 'attachment.xlsx';
}

function decode_mime(string $value): string {
    if (!function_exists('imap_mime_header_decode')) return $value;
    $parts = imap_mime_header_decode($value);
    $out   = '';
    foreach ($parts as $p) {
        $text    = $p->text ?? '';
        $charset = strtolower($p->charset ?? 'utf-8');
        if ($charset !== 'utf-8' && $charset !== 'default') {
            $text = mb_convert_encoding($text, 'UTF-8', $charset);
        }
        $out .= $text;
    }
    return $out;
}

/**
 * Сохраняет файл. Имя: {tab}_{YYYY-MM-DD}_{safe_original}.xlsx
 * Если файл с таким именем уже существует — пропускает (день уже загружен).
 * Возвращает true если файл сохранён, false если пропущен.
 */
function save_file(string $tab, string $day, string $original_name, string $content): bool {
    $safe = safe_filename($original_name);
    $dest = OUTPUT_DIR . "{$tab}_{$day}_{$safe}";
    if (file_exists($dest)) {
        echo "  [SKIP] Уже есть: " . basename($dest) . "\n";
        return false;
    }
    file_put_contents($dest, $content);
    echo "  [OK]   Сохранён: " . basename($dest) . "\n";
    return true;
}

// ── IMAP ──────────────────────────────────────────────────────────────────────

function fetch_from_imap(array $cfg, string $tab): void {
    if (empty($cfg['enabled'])) {
        echo "[SKIP] IMAP для '$tab' не включён.\n";
        return;
    }
    if (!function_exists('imap_open')) {
        echo "[ERROR] Расширение php-imap не установлено.\n";
        return;
    }

    $server   = trim($cfg['server'] ?? '');
    $port     = (int)($cfg['port'] ?? 993);
    $username = trim($cfg['username'] ?? '');
    $password = $cfg['password'] ?? '';
    $mailbox  = trim($cfg['mailbox'] ?? '') ?: 'INBOX';

    if (!$server || !$username || !$password) {
        echo "[SKIP] Не заполнены server/username/password для '$tab'.\n";
        return;
    }

    $sender_filter            = strtolower(trim($cfg['sender_filter']            ?? ''));
    $subject_filter           = strtolower(trim($cfg['subject_filter']           ?? ''));
    $subject_equals           = strtolower(trim($cfg['subject_equals']           ?? ''));
    $attachment_name_contains = strtolower(trim($cfg['attachment_name_contains'] ?? ''));
    $attachment_name_equals   = strtolower(trim($cfg['attachment_name_equals']   ?? ''));

    $mbox_str = "{{$server}:{$port}/imap/ssl}{$mailbox}";
    echo "[INFO] Подключаюсь: $mbox_str\n";

    $imap = @imap_open($mbox_str, $username, $password, 0, 1);
    if (!$imap) {
        echo "[ERROR] " . imap_last_error() . "\n";
        return;
    }

    // Поиск писем за последние DAYS_BACK дней
    $since = date('d-M-Y', strtotime('-' . DAYS_BACK . ' days'));
    $uids  = imap_search($imap, "SINCE \"$since\"") ?: [];

    echo "[INFO] Найдено писем за " . DAYS_BACK . " дней: " . count($uids) . "\n";

    // Группируем по дню: day => [uid, ...] (от старых к новым)
    // Берём последнее (самое позднее) письмо с вложением за каждый день.
    $by_day = [];   // ['2026-06-10' => ['uid' => N, 'ts' => T]]
    foreach ($uids as $uid) {
        $header = imap_headerinfo($imap, $uid);

        if ($sender_filter) {
            $from = strtolower($header->fromaddress ?? '');
            if (strpos($from, $sender_filter) === false) continue;
        }

        $subject = strtolower(decode_mime($header->subject ?? ''));
        if ($subject_equals && $subject !== $subject_equals) continue;
        if ($subject_filter && strpos($subject, $subject_filter) === false) continue;

        // Дата письма
        $ts  = strtotime($header->date ?? '') ?: 0;
        $day = date('Y-m-d', $ts);

        // Оставляем самое позднее за каждый день
        if (!isset($by_day[$day]) || $ts > $by_day[$day]['ts']) {
            $by_day[$day] = ['uid' => $uid, 'ts' => $ts];
        }
    }

    ksort($by_day);   // по возрастанию дат
    echo "[INFO] Дней с подходящими письмами: " . count($by_day) . "\n\n";

    foreach ($by_day as $day => $info) {
        $uid       = $info['uid'];
        $structure = imap_fetchstructure($imap, $uid);
        $parts     = $structure->parts ?? [];

        $saved = false;
        foreach ($parts as $i => $part) {
            $disp = strtolower($part->disposition ?? '');
            if ($disp !== 'attachment') continue;

            $filename = '';
            foreach ($part->dparameters ?? [] as $param) {
                if (strtolower($param->attribute) === 'filename') {
                    $filename = decode_mime($param->value);
                }
            }
            foreach ($part->parameters ?? [] as $param) {
                if (strtolower($param->attribute) === 'name') {
                    $filename = $filename ?: decode_mime($param->value);
                }
            }
            if (!$filename || !is_excel($filename)) continue;

            $lower = strtolower($filename);
            if ($attachment_name_equals   && $lower !== $attachment_name_equals)             continue;
            if ($attachment_name_contains && strpos($lower, $attachment_name_contains) === false) continue;

            $body = imap_fetchbody($imap, $uid, (string)($i + 1));
            switch ($part->encoding ?? 0) {
                case 3: $body = base64_decode($body);           break;
                case 4: $body = quoted_printable_decode($body); break;
            }
            if (!$body) continue;

            echo "  $day  ";
            save_file($tab, $day, $filename, $body);
            $saved = true;
            break;
        }
        if (!$saved) {
            echo "  $day  [SKIP] Нет Excel-вложения.\n";
        }
    }

    imap_close($imap);
}

// ── Локальная папка ───────────────────────────────────────────────────────────

/**
 * Для локальной папки: берём все файлы,
 * группируем по дню на основе mtime и сохраняем последний за каждый день.
 */
function fetch_from_folder(string $tab): void {
    $candidates = [__DIR__ . "/$tab", dirname(__DIR__) . "/$tab"];
    $folder     = null;
    foreach ($candidates as $c) {
        if (is_dir($c)) { $folder = $c; break; }
    }

    if (!$folder) {
        echo "[SKIP] Папка '$tab' не найдена рядом со скриптом.\n";
        return;
    }
    echo "[INFO] Читаю папку: $folder\n";

    // Собираем все Excel-файлы с их mtime
    $files = [];
    foreach (EXCEL_EXTS as $ext) {
        foreach (glob("$folder/*.$ext") ?: [] as $f) {
            $files[] = ['path' => $f, 'mtime' => filemtime($f)];
        }
    }

    if (!$files) {
        echo "[SKIP] В папке нет Excel-файлов.\n";
        return;
    }

    // Группируем по дню mtime, берём последний
    $by_day = [];
    foreach ($files as $f) {
        $day = date('Y-m-d', $f['mtime']);
        if (!isset($by_day[$day]) || $f['mtime'] > $by_day[$day]['mtime']) {
            $by_day[$day] = $f;
        }
    }

    // Ограничиваем последними DAYS_BACK днями
    $cutoff = strtotime('-' . DAYS_BACK . ' days');
    ksort($by_day);

    echo "[INFO] Дней с файлами: " . count($by_day) . "\n\n";

    foreach ($by_day as $day => $f) {
        if ($f['mtime'] < $cutoff) {
            echo "  $day  [SKIP] Старше " . DAYS_BACK . " дней.\n";
            continue;
        }
        $name = basename($f['path']);
        echo "  $day  ";
        $dest = OUTPUT_DIR . "{$tab}_{$day}_" . safe_filename($name);
        if (file_exists($dest)) {
            echo "[SKIP] Уже есть: " . basename($dest) . "\n";
            continue;
        }
        copy($f['path'], $dest);
        echo "[OK]   Скопирован: " . basename($dest) . "\n";
    }
}

// ── Точка входа ───────────────────────────────────────────────────────────────

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
