<?php
// Set the directory where uploaded files will be stored
$fileDir = '/tmp/clipfile';

// Ensure the directory exists
if (!is_dir($fileDir)) {
    mkdir($fileDir, 0777, true);
}

// Handle file uploads
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_FILES['uploadedFile'])) {
    $fileName = basename($_FILES['uploadedFile']['name']);
    $targetFile = $fileDir . '/' . $fileName;

    // Check if file upload was successful and move to the target directory
    if (move_uploaded_file($_FILES['uploadedFile']['tmp_name'], $targetFile)) {
        echo "File uploaded successfully! <a href=\"clipfile.php\">Go back</a>";
    } else {
        echo "Error uploading file.";
    }
    exit;
}

// Serve file download if requested
if (isset($_GET['download'])) {
    $fileName = basename($_GET['download']);
    $filePath = $fileDir . '/' . $fileName;

    // Check if file exists and serve it for download
    if (file_exists($filePath)) {
        header('Content-Description: File Transfer');
        header('Content-Type: application/octet-stream');
        header('Content-Disposition: attachment; filename="' . $fileName . '"');
        header('Expires: 0');
        header('Cache-Control: must-revalidate');
        header('Pragma: public');
        header('Content-Length: ' . filesize($filePath));
        readfile($filePath);
        exit;
    } else {
        echo "File not found.";
        exit;
    }
}

// Get the list of files in the directory
$files = array_diff(scandir($fileDir), array('.', '..'));

?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clipfile</title>
</head>
<body>
    <h1>Clipfile</h1>

    <!-- File upload form -->
    <form action="clipfile.php" method="POST" enctype="multipart/form-data">
        <label for="uploadedFile">Select a file to upload:</label>
        <input type="file" name="uploadedFile" id="uploadedFile" required>
        <button type="submit">Upload File</button>
    </form>

    <h2>Available Files:</h2>
    <?php if (count($files) > 0): ?>
        <ul>
            <?php foreach ($files as $file): ?>
                <li><a href="clipfile.php?download=<?php echo urlencode($file); ?>"><?php echo htmlspecialchars($file); ?></a></li>
            <?php endforeach; ?>
        </ul>
    <?php else: ?>
        <p>No files available.</p>
    <?php endif; ?>
</body>
</html>
