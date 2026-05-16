import json
import time

from scenarios.common import aws_client


def run():
    ec2 = aws_client("ec2")

    resp = ec2.describe_instances(
        Filters=[{"Name": "tag:Name", "Values": ["wordpress-server"]}]
    )
    reservations = resp.get("Reservations", [])
    if not reservations or not reservations[0].get("Instances"):
        print("ERROR: No WordPress EC2 instance found. Run setup first.")
        return

    instance = reservations[0]["Instances"][0]
    instance_id = instance["InstanceId"]
    state = instance["State"]["Name"]
    public_ip = instance.get("PublicIpAddress", "N/A")
    private_ip = instance.get("PrivateIpAddress", "N/A")
    launch_time = instance.get("LaunchTime", "N/A").strftime("%Y-%m-%d %H:%M:%S")

    print(f"Instance ID:  {instance_id}")
    print(f"State:        {state}")
    print(f"Public IP:    {public_ip}")
    print(f"Private IP:   {private_ip}")
    print(f"Launch Time:  {launch_time}")
    print(f"Instance Type: {instance.get('InstanceType', 'N/A')}")
    print(f"VPC ID:       {instance.get('VpcId', 'N/A')}")
    print(f"Subnet ID:    {instance.get('SubnetId', 'N/A')}")
    print()

    if state == "running":
        print("Instance is running. You can access WordPress via:")
        print(f"  Web:  http://{public_ip}/wordpress/")
        print(f"  SSH:  ssh -i wordpress-key.pem ec2-user@{public_ip}")
        print()
        print("UserData output (check if WordPress setup succeeded):")
        print(f"  ssh -i wordpress-key.pem ec2-user@{public_ip} 'sudo cat /var/log/userdata.log'")
    else:
        print(f"Instance is in state: {state}. It may still be starting up.")


if __name__ == "__main__":
    run()
