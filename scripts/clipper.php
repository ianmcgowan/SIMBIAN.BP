<?php
// Set the directory where files will be stored
$storageDir = '/tmp/clipper';

// Ensure the directory exists
if (!is_dir($storageDir)) {
    mkdir($storageDir, 0777, true);
}

// Get the session name from the request (e.g., ?session=your_session_name)
$sessionName = isset($_GET['session']) ? preg_replace('/[^a-zA-Z0-9_-]/', '', $_GET['session']) : '';

// Handle POST requests to save content
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $sessionName) {
    $content = $_POST['content'] ?? '';
    file_put_contents("$storageDir/$sessionName.txt", $content);
    ?>
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Clipper - Saved</title>
        <meta http-equiv="refresh" content="2;url=clipper.php?session=<?php echo htmlspecialchars($sessionName); ?>">
    </head>
    <body>
        <h1>Clipper</h1>
        <p>Content saved! Redirecting back to your session...</p>
    </body>
    </html>
    <?php
    exit;
}

// Handle GET requests to retrieve content
if ($sessionName) {
    $filePath = "$storageDir/$sessionName.txt";
    $content = file_exists($filePath) ? file_get_contents($filePath) : '';
    ?>
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Clipper</title>
        <style>
            textarea {
                width: 80%;
                max-width: 100%;
                box-sizing: border-box;
            }
            .button-container {
                display: flex;
                gap: 10px;
                margin-top: 10px;
            }
        </style>
        <script>
            function copyToClipboard() {
                const textarea = document.getElementById('content');
                textarea.select();
                document.execCommand('copy');
                alert('Text copied to clipboard!');
            }
        </script>
    </head>
    <body>
        <h1>Clipper</h1>
        <form method="POST" action="clipper.php?session=<?php echo htmlspecialchars($sessionName); ?>">
            <textarea id="content" name="content" rows="20"><?php echo htmlspecialchars($content); ?></textarea><br>
            <div class="button-container">
                <button type="submit">Save</button>
                <?php if ($content): ?>
                    <button type="button" onclick="copyToClipboard()">Copy</button>
                <?php endif; ?>
            </div>
        </form>
        <p>Access this session again by visiting: <a href="clipper.php?session=<?php echo htmlspecialchars($sessionName); ?>">clipper.php?session=<?php echo htmlspecialchars($sessionName); ?></a></p>
    </body>
    </html>
    <?php
    exit;
}

// If no session is provided, display a session input form
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clipper</title>
</head>
<body>
    <h1>Clipper</h1>
    <form method="GET" action="clipper.php">
        <label for="session">Enter a session name:</label>
        <input type="text" name="session" id="session" required>
        <button type="submit">Go</button>
    </form>
</body>
</html>
