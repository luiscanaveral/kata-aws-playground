import json

from scenarios.common import aws_client


def run():
    apigw = aws_client("apigateway")
    appcfg = aws_client("appconfig")

    apis = apigw.get_rest_apis()
    api = next(
        (a for a in apis.get("items", []) if a["name"] == "feature-flags-api"),
        None,
    )
    if not api:
        print("ERROR: Feature flags API not found. Deploy infrastructure first.")
        return

    api_id = api["id"]
    url = f"http://localhost:4566/restapis/{api_id}/v1/_user_request_"

    apps = appcfg.list_applications()
    app = next((a for a in apps.get("Items", []) if a["Name"] == "feature-flags-app"), None)
    app_id = app["Id"] if app else "?"

    profiles = appcfg.list_configuration_profiles(ApplicationId=app_id)
    profile = next(
        (p for p in profiles.get("Items", []) if p["Name"] == "ui-layout"),
        None,
    )
    profile_id = profile["Id"] if profile else "?"

    print("=" * 60)
    print("FEATURE FLAGS — AppConfig Demo")
    print("=" * 60)
    print()
    print(f"  Frontend: {url}/")
    print(f"  API:      {url}/flags")
    print(f"  App ID:   {app_id}")
    print(f"  Profile:  {profile_id}")
    print()
    print("  Open the frontend in your browser.")
    print("  Toggle widgets to create new AppConfig versions.")
    print("  Each toggle deploys a new config via AppConfig.")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    try:
        import urllib.request
        resp = urllib.request.urlopen(f"{url}/flags")
        flags = json.loads(resp.read().decode())
        widgets = flags.get("widgets", [])
        visible = [w for w in widgets if w.get("visible")]
        hidden = [w for w in widgets if not w.get("visible")]
        print(f"  Current state: {len(visible)} visible, {len(hidden)} hidden")
        for w in sorted(widgets, key=lambda x: x.get("order", 999)):
            status = "ON" if w.get("visible") else "OFF"
            print(f"    [{status}] #{w['id']}: {w['title']} (pos {w['order']})")
        print()
        print(f"  Open: {url}/")
    except Exception as e:
        print(f"  Error fetching flags: {e}")

    import time
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print()
        print("  Done.")


if __name__ == "__main__":
    run()
