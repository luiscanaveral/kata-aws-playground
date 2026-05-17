import json
import os

import boto3

APP_ID = os.environ.get("APPCFG_APP_ID", "")
ENV_ID = os.environ.get("APPCFG_ENV_ID", "")
PROFILE_ID = os.environ.get("APPCFG_PROFILE_ID", "")
STRATEGY_ID = os.environ.get("APPCFG_STRATEGY_ID", "AppConfig.Quick")
FLOCI = os.environ.get("AWS_ENDPOINT_URL", "http://floci:4566")

REGION = "us-east-1"
KW = dict(
    endpoint_url=FLOCI,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

DEFAULT_FLAGS = {
    "widgets": [
        {"id": "weather", "title": "Weather", "visible": True, "order": 1},
        {"id": "news", "title": "News Feed", "visible": True, "order": 2},
        {"id": "stocks", "title": "Stock Ticker", "visible": False, "order": 3},
        {"id": "calendar", "title": "Calendar", "visible": True, "order": 4},
        {"id": "todo", "title": "To-Do List", "visible": True, "order": 5},
        {"id": "analytics", "title": "Analytics", "visible": False, "order": 6},
    ],
    "theme": "light",
}


def _fetch_flags() -> dict:
    client = boto3.client("appconfigdata", **KW)
    try:
        session = client.start_configuration_session(
            ApplicationIdentifier=APP_ID,
            EnvironmentIdentifier=ENV_ID,
            ConfigurationProfileIdentifier=PROFILE_ID,
        )
        token = session["InitialConfigurationToken"]
        resp = client.get_latest_configuration(ConfigurationToken=token)
        content = resp["Configuration"].read()
        return json.loads(content)
    except Exception as e:
        print(f"AppConfigData fetch failed: {e}")
        return dict(DEFAULT_FLAGS)


def _update_flags(new_flags: dict) -> dict:
    client = boto3.client("appconfig", **KW)
    content = json.dumps(new_flags)
    version = client.create_hosted_configuration_version(
        ApplicationId=APP_ID,
        ConfigurationProfileId=PROFILE_ID,
        Content=content,
        ContentType="application/json",
    )
    vn = version["VersionNumber"]
    dep = client.start_deployment(
        ApplicationId=APP_ID,
        EnvironmentId=ENV_ID,
        DeploymentStrategyId=STRATEGY_ID,
        ConfigurationProfileId=PROFILE_ID,
        ConfigurationVersion=str(vn),
    )
    return {"version": vn, "deployment": dep.get("DeploymentNumber", 0)}


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Feature Flags Demo</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background: #f0f2f5; min-height: 100vh; }
    .header { background: #fff; border-bottom: 1px solid #ddd; padding: 16px 24px;
              display: flex; align-items: center; justify-content: space-between;
              position: sticky; top: 0; z-index: 10; }
    .header h1 { font-size: 22px; color: #1a1a2e; }
    .header .badge { background: #6366f1; color: #fff; font-size: 11px;
                     padding: 3px 10px; border-radius: 12px; margin-left: 8px; }
    .container { max-width: 960px; margin: 0 auto; padding: 20px 16px; }
    .controls { background: #fff; border-radius: 10px; padding: 16px; margin-bottom: 20px;
                box-shadow: 0 1px 3px rgba(0,0,0,.08); display: flex; flex-wrap: wrap;
                gap: 10px; align-items: center; }
    .controls label { display: flex; align-items: center; gap: 6px; font-size: 13px;
                      cursor: pointer; padding: 6px 12px; border-radius: 6px;
                      border: 1px solid #e0e0e0; user-select: none; }
    .controls label.active { background: #eef2ff; border-color: #6366f1; }
    .controls label input { accent-color: #6366f1; }
    .btn { background: #6366f1; color: #fff; border: none; padding: 8px 20px;
           border-radius: 6px; cursor: pointer; font-size: 13px; }
    .btn:hover { background: #4f46e5; }
    .btn:disabled { opacity: .5; cursor: default; }
    .btn.outline { background: #fff; color: #6366f1; border: 1px solid #6366f1; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .widget { background: #fff; border-radius: 10px; padding: 20px;
              box-shadow: 0 1px 3px rgba(0,0,0,.08); transition: all .3s; }
    .widget h3 { font-size: 15px; color: #1a1a2e; margin-bottom: 6px; }
    .widget p { font-size: 13px; color: #666; }
    .widget .id-badge { font-size: 10px; color: #999; background: #f5f5f5;
                        padding: 2px 8px; border-radius: 10px; }
    .empty { text-align: center; color: #999; padding: 40px; grid-column: 1 / -1; }
    .info { background: #fefce8; border: 1px solid #fde68a; border-radius: 8px;
            padding: 12px 16px; font-size: 12px; color: #92400e; margin-top: 16px; }
    .toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
             background: #1a1a2e; color: #fff; padding: 10px 24px; border-radius: 8px;
             font-size: 14px; opacity: 0; transition: opacity .3s; pointer-events: none; }
    .toast.show { opacity: 1; }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>Feature Flags <span class="badge">AppConfig</span></h1>
    </div>
    <button class="btn" id="refreshBtn" onclick="loadFlags()">Refresh</button>
  </div>
  <div class="container">
    <div class="controls" id="controls"></div>
    <div class="grid" id="grid"></div>
    <div class="info" id="info"></div>
  </div>
  <div class="toast" id="toast"></div>

  <script>
    let currentFlags = null;
    let saving = false;

    async function loadFlags() {
      try {
        const r = await fetch('/flags');
        const data = await r.json();
        currentFlags = data;
        render(data);
      } catch (e) {
        toast('Failed to load flags');
      }
    }

    function render(data) {
      const widgets = (data.widgets || []).sort((a, b) => a.order - b.order);
      const grid = document.getElementById('grid');

      const visible = widgets.filter(w => w.visible);
      if (visible.length === 0) {
        grid.innerHTML = '<div class="empty">All widgets hidden. Toggle some on above.</div>';
      } else {
        grid.innerHTML = visible.map(w =>
          '<div class="widget" style="order:' + w.order + '">'
          + '<div style="display:flex;justify-content:space-between;align-items:center">'
          + '<h3>' + esc(w.title) + '</h3>'
          + '<span class="id-badge">#' + esc(w.id) + ' · pos ' + w.order + '</span>'
          + '</div>'
          + '<p>This is the <strong>' + esc(w.title) + '</strong> widget. '
          + 'Its visibility and position are controlled by AppConfig feature flags.</p>'
          + '</div>'
        ).join('');
      }

      const controls = document.getElementById('controls');
      controls.innerHTML = '<span style="font-size:13px;font-weight:600;margin-right:4px">Toggle widgets:</span>'
        + widgets.map(w =>
          '<label class="' + (w.visible ? 'active' : '') + '">'
          + '<input type="checkbox" ' + (w.visible ? 'checked' : '')
          + ' onchange="toggleWidget(\'' + w.id + '\', this.checked)">'
          + esc(w.title)
          + '</label>'
        ).join('')
        + '<button class="btn outline" onclick="loadFlags()">Reset view</button>';

      const info = document.getElementById('info');
      info.innerHTML = '<strong>AppConfig</strong> flags loaded via <code>AppConfigData</code>. '
        + 'Visible: ' + visible.length + '/' + widgets.length + ' widgets. '
        + 'Toggle a checkbox to create a new config version and deploy.';
    }

    async function toggleWidget(id, visible) {
      if (saving || !currentFlags) return;
      saving = true;
      const newFlags = JSON.parse(JSON.stringify(currentFlags));
      const w = newFlags.widgets.find(x => x.id === id);
      if (!w) return;
      w.visible = visible;

      try {
        const r = await fetch('/flags', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(newFlags),
        });
        const result = await r.json();
        toast('Deployed v' + result.version);
        await loadFlags();
      } catch (e) {
        toast('Failed to update flags');
      }
      saving = false;
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

    loadFlags();
  </script>
</body>
</html>"""


def _ok(data):
    return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(data)}


def _html(body):
    return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": body}


def _err(code, msg):
    return {"statusCode": code, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": msg})}


def handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "/")

    if method == "GET" and path == "/":
        return _html(HTML)

    if method == "GET" and path == "/flags":
        flags = _fetch_flags()
        return _ok(flags)

    if method == "POST" and path == "/flags":
        body = event.get("body", "{}")
        try:
            new_flags = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return _err(400, "Invalid JSON body")
        result = _update_flags(new_flags)
        return _ok(result)

    return _err(404, "Not found")
