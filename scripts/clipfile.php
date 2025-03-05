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
    $base64Encode = isset($_POST['base64Encode']);

    // Check if file upload was successful and move to the target directory
    if (move_uploaded_file($_FILES['uploadedFile']['tmp_name'], $targetFile)) {
        if ($base64Encode) {
            // Read the file and encode it in Base64
            $fileData = file_get_contents($targetFile);
            $base64Data = base64_encode($fileData);

            // Save the Base64 encoded data as a .txt file
            $base64File = $fileDir . '/' . pathinfo($fileName, PATHINFO_FILENAME) . '.txt';
            file_put_contents($base64File, $base64Data);

            echo "File uploaded and Base64 encoded successfully! <a href=\"clipfile.php\">Go back</a>";
        } else {
            echo "File uploaded successfully! <a href=\"clipfile.php\">Go back</a>";
        }
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
    <style>
        .powershell-command {
            font-family: monospace;
            background-color: #f0f0f0;
            padding: 5px;
            border: 1px solid #ddd;
            display: inline-block;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <h1>Clipfile</h1>

    <!-- File upload form -->
    <form action="clipfile.php" method="POST" enctype="multipart/form-data">
        <label for="uploadedFile">Select a file to upload:</label>
        <input type="file" name="uploadedFile" id="uploadedFile" required><br><br>
        <input type="checkbox" name="base64Encode" id="base64Encode">
        <label for="base64Encode">Base64 Encode</label><br><br>
        <button type="submit">Upload File</button>
    </form>

    <h2>Available Files:</h2>
    <?php if (count($files) > 0): ?>
        <ul>
            <?php foreach ($files as $file): ?>
                <li>
                    <a href="clipfile.php?download=<?php echo urlencode($file); ?>"><?php echo htmlspecialchars($file); ?></a>
                    <?php if (pathinfo($file, PATHINFO_EXTENSION) === 'txt'): ?>
                        <div class="powershell-command">
                            powershell -Command "[System.IO.File]::WriteAllBytes('<?php echo pathinfo($file, PATHINFO_FILENAME); ?>', [System.Convert]::FromBase64String((Get-Content -Path '<?php echo $fileDir . '/' . $file; ?>' -Raw)))"
                        </div>
                    <?php endif; ?>
                </li>
            <?php endforeach; ?>
        </ul>
    <?php else: ?>
        <p>No files available.</p>
    <?php endif; ?>
</body>
</html>
root@simbian:/var/www/simbian.org/html# cat > clipfile.php
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
    $base64Encode = isset($_POST['base64Encode']);

    // Check if file upload was successful and move to the target directory
    if (move_uploaded_file($_FILES['uploadedFile']['tmp_name'], $targetFile)) {
        if ($base64Encode) {
            // Read the file and encode it in Base64
            $fileData = file_get_contents($targetFile);
            $base64Data = base64_encode($fileData);

            // Save the Base64 encoded data as a .txt file
            $base64File = $fileDir . '/' . pathinfo($fileName, PATHINFO_FILENAME) . '.txt';
            file_put_contents($base64File, $base64Data);

            echo "File uploaded and Base64 encoded successfully! <a href=\"clipfile.php\">Go back</a>";
        } else {
            echo "File uploaded successfully! <a href=\"clipfile.php\">Go back</a>";
        }
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
    <style>
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
        .powershell-command {
            font-family: monospace;
            background-color: #f0f0f0;
            padding: 5px;
            border: 1px solid #ddd;
            display: inline-block;
            margin-top: 5px;
            width: 100%;
        }
    </style>
</head>
<body>
    <h1>Clipfile</h1>

    <!-- File upload form -->
    <form action="clipfile.php" method="POST" enctype="multipart/form-data">
        <label for="uploadedFile">Select a file to upload:</label>
        <input type="file" name="uploadedFile" id="uploadedFile" required><br><br>
        <input type="checkbox" name="base64Encode" id="base64Encode">
        <label for="base64Encode">Base64 Encode</label><br><br>
        <button type="submit">Upload File</button>
    </form>

    <h2>Available Files:</h2>
    <?php if (count($files) > 0): ?>
        <table>
            <tr>
                <th>File Name</th>
                <th>Download</th>
                <th>PowerShell Command (if applicable)</th>
            </tr>
            <?php foreach ($files as $file): ?>
                <tr>
                    <td><?php echo htmlspecialchars($file); ?></td>
                    <td><a href="clipfile.php?download=<?php echo urlencode($file); ?>">Download</a></td>
                    <td>
                        <?php if (pathinfo($file, PATHINFO_EXTENSION) === 'txt'): ?>
                            <div class="powershell-command">
                                powershell -Command "[System.IO.File]::WriteAllBytes('<?php echo pathinfo($file, PATHINFO_FILENAME); ?>', [System.Convert]::FromBase64String((Get-Content -Path '<?php echo $file; ?>' -Raw)))"
                            </div>
                        <?php endif; ?>
                    </td>
                </tr>
            <?php endforeach; ?>
        </table>
    <?php else: ?>
        <p>No files available.</p>
    <?php endif; ?>
</body>
</html>
