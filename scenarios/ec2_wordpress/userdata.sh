#!/bin/bash
set -euxo pipefail

exec > /var/log/userdata.log 2>&1

dnf update -y
dnf install -y httpd php php-mysqlnd php-json php-xml php-mbstring php-gd

systemctl enable httpd
systemctl start httpd

WORDPRESS_VERSION="6.7"
WP_DIR="/var/www/html/wordpress"

mkdir -p "$WP_DIR"
cat > "$WP_DIR/index.php" << 'PHPEOF'
<?php
$ip = $_SERVER['SERVER_ADDR'] ?? gethostname();
$hostname = gethostname();
$date = date('Y-m-d H:i:s');
?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>EC2 WordPress - Floci Playground</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
           min-height: 100vh; display: flex; align-items: center; justify-content: center; }
    .card { background: white; border-radius: 16px; padding: 40px; max-width: 600px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3); text-align: center; }
    h1 { color: #21759b; font-size: 28px; margin-bottom: 8px; }
    .logo { font-size: 48px; margin-bottom: 16px; }
    .badge { display: inline-block; background: #21759b; color: white; padding: 4px 12px;
             border-radius: 20px; font-size: 12px; margin-bottom: 20px; }
    .info { background: #f0f0f1; border-radius: 8px; padding: 16px; text-align: left;
            font-family: monospace; font-size: 13px; margin: 20px 0; }
    .info dt { color: #666; font-size: 11px; text-transform: uppercase; margin-top: 8px; }
    .info dd { color: #333; margin: 2px 0 0 0; word-break: break-all; }
    .info dd:first-of-type { margin-top: 0; }
    .status { display: inline-block; padding: 8px 24px; background: #46b450; color: white;
              border-radius: 8px; font-weight: 600; margin-top: 16px; }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">&#9893;</div>
    <h1>EC2 WordPress</h1>
    <div class="badge">Running on Floci EC2</div>
    <p>Your EC2 instance is running Apache + PHP and serving this WordPress-style landing page.</p>
    <dl class="info">
      <dt>Instance</dt>
      <dd><?= $hostname ?></dd>
      <dt>Private IP</dt>
      <dd><?= $ip ?></dd>
      <dt>Server Time</dt>
      <dd><?= $date ?></dd>
      <dt>PHP Version</dt>
      <dd><?= phpversion() ?></dd>
    </dl>
    <div class="status">&#10003; Instance Healthy</div>
  </div>
</body>
</html>
PHPEOF

chown -R apache:apache /var/www/html/
chmod 755 "$WP_DIR/index.php"

echo "WordPress EC2 instance setup complete"
