import base64
import os

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class Ec2WordpressStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.CfnVPC(
            self,
            "WordpressVpc",
            cidr_block="10.0.0.0/16",
            tags=[{"key": "Name", "value": "wordpress-vpc"}],
        )

        subnet = ec2.CfnSubnet(
            self,
            "WordpressSubnet",
            vpc_id=vpc.ref,
            cidr_block="10.0.1.0/24",
            tags=[{"key": "Name", "value": "wordpress-subnet"}],
        )

        igw = ec2.CfnInternetGateway(
            self,
            "WordpressIgw",
            tags=[{"key": "Name", "value": "wordpress-igw"}],
        )
        ec2.CfnVPCGatewayAttachment(
            self,
            "WordpressIgwAttach",
            vpc_id=vpc.ref,
            internet_gateway_id=igw.ref,
        )

        rt = ec2.CfnRouteTable(
            self,
            "WordpressRouteTable",
            vpc_id=vpc.ref,
        )
        ec2.CfnRoute(
            self,
            "WordpressDefaultRoute",
            route_table_id=rt.ref,
            destination_cidr_block="0.0.0.0/0",
            gateway_id=igw.ref,
        )
        ec2.CfnSubnetRouteTableAssociation(
            self,
            "WordpressRtAssoc",
            route_table_id=rt.ref,
            subnet_id=subnet.ref,
        )

        sg = ec2.CfnSecurityGroup(
            self,
            "WordpressSg",
            group_description="WordPress security group",
            vpc_id=vpc.ref,
            security_group_ingress=[
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol="tcp",
                    from_port=22,
                    to_port=22,
                    cidr_ip="0.0.0.0/0",
                ),
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol="tcp",
                    from_port=80,
                    to_port=80,
                    cidr_ip="0.0.0.0/0",
                ),
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol="tcp",
                    from_port=443,
                    to_port=443,
                    cidr_ip="0.0.0.0/0",
                ),
            ],
        )

        ec2.CfnKeyPair(
            self,
            "WordpressKeyPair",
            key_name="wordpress-key",
        )

        script_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "scenarios",
            "ec2_wordpress",
            "userdata.sh",
        )
        with open(script_path) as f:
            userdata = f.read()
        userdata_b64 = base64.b64encode(userdata.encode()).decode()

        ec2.CfnInstance(
            self,
            "WordpressInstance",
            instance_type="t2.micro",
            image_id="ami-0abcdef1234567890",
            key_name="wordpress-key",
            security_group_ids=[sg.ref],
            subnet_id=subnet.ref,
            user_data=userdata_b64,
            tags=[{"key": "Name", "value": "wordpress-server"}],
        )
