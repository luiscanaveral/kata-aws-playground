import base64
import json
import os
import time

from scenarios.common import account_id, aws_client


def setup():
    ec2_client = aws_client("ec2")
    iam_client = aws_client("iam")
    sts_client = aws_client("sts")

    aws_account_id = account_id()

    try:
        iam_client.create_role(
            RoleName="ec2-wordpress-role",
            AssumeRolePolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}',
        )
        iam_client.put_role_policy(
            RoleName="ec2-wordpress-role",
            PolicyName="ec2-wordpress-policy",
            PolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:Get*","s3:List*","logs:*"],"Resource":"*"}]}',
        )
        iam_client.create_instance_profile(InstanceProfileName="ec2-wordpress-profile")
        iam_client.add_role_to_instance_profile(
            InstanceProfileName="ec2-wordpress-profile",
            RoleName="ec2-wordpress-role",
        )
        print("Created IAM role + instance profile: ec2-wordpress-role")
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("IAM role/profile already exists")

    vpc = ec2_client.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    ec2_client.create_tags(Resources=[vpc_id], Tags=[{"Key": "Name", "Value": "wordpress-vpc"}])
    print(f"VPC created: {vpc_id}")

    subnet = ec2_client.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
    subnet_id = subnet["Subnet"]["SubnetId"]
    ec2_client.create_tags(Resources=[subnet_id], Tags=[{"Key": "Name", "Value": "wordpress-subnet"}])
    print(f"Subnet created: {subnet_id}")

    igw = ec2_client.create_internet_gateway()
    igw_id = igw["InternetGateway"]["InternetGatewayId"]
    ec2_client.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
    print(f"Internet Gateway created + attached: {igw_id}")

    rt = ec2_client.create_route_table(VpcId=vpc_id)
    rt_id = rt["RouteTable"]["RouteTableId"]
    ec2_client.create_route(RouteTableId=rt_id, DestinationCidrBlock="0.0.0.0/0", GatewayId=igw_id)
    ec2_client.associate_route_table(RouteTableId=rt_id, SubnetId=subnet_id)
    print(f"Route table created: {rt_id}")

    sg = ec2_client.create_security_group(
        GroupName="wordpress-sg",
        Description="WordPress security group",
        VpcId=vpc_id,
    )
    sg_id = sg["GroupId"]
    ec2_client.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[
            {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
            {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
            {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
        ],
    )
    print(f"Security group created: {sg_id}")

    try:
        kp = ec2_client.create_key_pair(KeyName="wordpress-key")
        private_key = kp["KeyMaterial"]
        key_path = os.path.join(os.path.dirname(__file__), "..", "..", "wordpress-key.pem")
        with open(key_path, "w") as f:
            f.write(private_key)
        os.chmod(key_path, 0o400)
        print(f"Key pair created: wordpress-key (saved to wordpress-key.pem)")
    except ec2_client.exceptions.KeyPairExists:
        print("Key pair already exists")

    script_path = os.path.join(os.path.dirname(__file__), "userdata.sh")
    with open(script_path) as f:
        userdata = f.read()
    userdata_b64 = base64.b64encode(userdata.encode()).decode()

    instances = ec2_client.run_instances(
        ImageId="ami-0abcdef1234567890",
        InstanceType="t2.micro",
        KeyName="wordpress-key",
        MinCount=1,
        MaxCount=1,
        SecurityGroupIds=[sg_id],
        SubnetId=subnet_id,
        UserData=userdata_b64,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": "wordpress-server"}],
            }
        ],
    )
    instance_id = instances["Instances"][0]["InstanceId"]
    print(f"EC2 instance launched: {instance_id}")

    print("Waiting for instance to reach running state...")
    for _ in range(30):
        desc = ec2_client.describe_instances(InstanceIds=[instance_id])
        state = desc["Reservations"][0]["Instances"][0]["State"]["Name"]
        if state == "running":
            break
        time.sleep(2)
    else:
        print("WARNING: Instance did not reach running state within 60s")

    desc = ec2_client.describe_instances(InstanceIds=[instance_id])
    inst = desc["Reservations"][0]["Instances"][0]
    public_ip = inst.get("PublicIpAddress", "N/A")
    private_ip = inst.get("PrivateIpAddress", "N/A")

    print(f"Instance {instance_id} is {inst['State']['Name']}")
    print(f"  Public IP:  {public_ip}")
    print(f"  Private IP: {private_ip}")

    return {
        "instance_id": instance_id,
        "public_ip": public_ip,
        "private_ip": private_ip,
        "vpc_id": vpc_id,
        "subnet_id": subnet_id,
        "sg_id": sg_id,
    }


if __name__ == "__main__":
    ctx = setup()
    print(f"\nWordPress EC2 instance ready!")
    print(f"  SSH: ssh -i wordpress-key.pem ec2-user@{ctx['public_ip']}")
    print(f"  Web: http://{ctx['public_ip']}/wordpress/")
