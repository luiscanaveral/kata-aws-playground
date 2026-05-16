import json
import os

import boto3

TABLE_NAME = os.environ.get("FEED_TABLE", "social_posts")
FLOCI_ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://floci:4566")

dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url=FLOCI_ENDPOINT,
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)
table = dynamodb.Table(TABLE_NAME)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Social Feed</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background: #f0f2f5; min-height: 100vh; }
    .header { background: #fff; border-bottom: 1px solid #ddd; padding: 16px 24px;
              display: flex; align-items: center; justify-content: space-between;
              position: sticky; top: 0; z-index: 10; }
    .header h1 { font-size: 22px; color: #1a1a2e; }
    .header span { color: #666; font-size: 13px; }
    .btn { background: #1a1a2e; color: #fff; border: none; padding: 8px 20px;
           border-radius: 6px; cursor: pointer; font-size: 14px; }
    .btn:hover { background: #16213e; }
    .btn:disabled { opacity: .5; cursor: default; }
    .container { max-width: 600px; margin: 24px auto; padding: 0 16px; }
    .post { background: #fff; border-radius: 10px; padding: 16px 20px; margin-bottom: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,.08); }
    .post .username { font-weight: 600; color: #1a1a2e; font-size: 15px; }
    .post .time { color: #999; font-size: 12px; margin-left: 8px; }
    .post .content { margin-top: 8px; color: #333; font-size: 15px; line-height: 1.5; }
    .empty { text-align: center; color: #999; padding: 60px 0; font-size: 15px; }
    .toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
             background: #1a1a2e; color: #fff; padding: 10px 24px; border-radius: 8px;
             font-size: 14px; opacity: 0; transition: opacity .3s; pointer-events: none; }
    .toast.show { opacity: 1; }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>Social Feed</h1>
      <span id="counter">0 posts</span>
    </div>
    <button class="btn" id="refreshBtn" onclick="refresh()">Refresh</button>
  </div>
  <div class="container" id="feed"></div>
  <div class="toast" id="toast"></div>

  <script>
    let loading = false;

    async function refresh() {
      if (loading) return;
      loading = true;
      const btn = document.getElementById('refreshBtn');
      const feed = document.getElementById('feed');
      const counter = document.getElementById('counter');
      btn.disabled = true;
      btn.textContent = 'Loading...';

      try {
        const res = await fetch('/feed');
        const data = await res.json();
        const posts = data.posts || [];

        counter.textContent = posts.length + ' posts';

        if (posts.length === 0) {
          feed.innerHTML = '<div class="empty">No posts yet. Waiting for publisher...</div>';
        } else {
          feed.innerHTML = posts.map(p => {
            const t = new Date(p.created_at * 1000).toLocaleString();
            return '<div class="post">'
              + '<span class="username">@' + esc(p.username) + '</span>'
              + '<span class="time">' + t + '</span>'
              + '<div class="content">' + esc(p.content) + '</div>'
              + '</div>';
          }).join('');
        }

        toast('Updated — ' + posts.length + ' posts');
      } catch (e) {
        toast('Failed to load feed');
      }

      btn.disabled = false;
      btn.textContent = 'Refresh';
      loading = false;
    }

    function esc(s) { return (s || '').replace(/[&<>"]/g, function(m) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]; });
    }

    function toast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 2000);
    }

    refresh();
    setInterval(refresh, 8000);
  </script>
</body>
</html>"""


def handler(event, context):
    path = event.get("path", "/")

    if path == "/feed":
        response = table.scan(
            limit=50,
            projectionExpression="post_id,username,content,created_at",
        )
        items = response.get("Items", [])
        items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"posts": items}),
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": HTML,
    }
