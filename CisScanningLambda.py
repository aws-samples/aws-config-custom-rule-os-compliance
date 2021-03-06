#
# This file made available under CC0 1.0 Universal (https://creativecommons.org/publicdomain/zero/1.0/legalcode)
#

import boto3
import botocore
import json
import logging
import time
import re
from botocore.exceptions import ClientError

def evaluate_compliance(configuration_item):
    region     = configuration_item['awsRegion']
    ssm_client = boto3.client('ssm', region_name=region)
    instance_id = configuration_item['configuration']['instanceId']

    ssm_response = ssm_client.send_command(
        InstanceIds=[ instance_id ],
        DocumentName="AWS-RunInspecChecks",
        Parameters={
            'sourceInfo':[ '{ "owner":"dev-sec", "repository":"cis-dil-benchmark", "path": "", "getOptions" : "branch:master", "tokenInfo":"{{ssm-secure:github-personal-token-InSpec}}" }' ],
            'sourceType': [ 'GitHub' ]
        })
    command_id = ssm_response['Command']['CommandId']

    ctr=0
    while True:
        try:
            output = ssm_client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
                PluginName='runInSpecLinux'
                )
            status = output['Status']
            if status == 'Success':
                print ("cis-dil-benchmark scan completed successfully. Checking for NON_COMPLIANT items.")
                message = output['StandardOutputContent']
                x = re.search("and 0 non-compliant",message)
                if not x:
                    annotation = "The ec2 instance " + instance_id +" is NOT compliant"
                    compliance_type = 'NON_COMPLIANT'
                else:
                    annotation = "The ec2 instance " + instance_id +" is compliant"
                    compliance_type = 'COMPLIANT'
                print (annotation)
            elif status == 'Delivery Timed Out' or status == 'Execution Timed Out' or status == 'Failed' or status == 'Canceled' or status == 'Undeliverable' or status == 'Terminated':
                annotation = "cis-dil-benchmark scan was not successful. Ec2 instance " + instance_id + "'s state could not be determined.  Marked NON_COMPLIANT for now."
                compliance_type = 'NON_COMPLIANT'
            break
        except ClientError as e:
            ctr += 1
            print('waiting for the scan result. %d'%ctr)
            time.sleep(1)
    return {
        "compliance_type": compliance_type,
        "annotation": annotation
    }

def lambda_handler(event, context):
    print ("event: ",event)
    invoking_event     = json.loads(event['invokingEvent'])
    configuration_item = invoking_event["configurationItem"]
    if configuration_item['resourceType'] != "AWS::EC2::Instance":
        print ("DEBUG: I can only evaluate EC2 instances")
        evaluation = {
            "compliance_type": "NOT_APPLICABLE",
            "annotation": "Wrong resource type"
        }
    elif configuration_item['configuration'] == None or configuration_item['configuration']['instanceId'] == None:
        print("DEBUG: cannot retrieve instanceId")
        evaluation = {
            "compliance_type": "INSUFFICIENT_DATA",
            "annotation": "configurationItem array is empty or instanceId missing"
        };
    else:
        evaluation = evaluate_compliance(configuration_item)

    config   = boto3.client('config')
    response = config.put_evaluations(
       Evaluations=[
           {
               'ComplianceResourceType': invoking_event['configurationItem']['resourceType'],
               'ComplianceResourceId':   invoking_event['configurationItem']['resourceId'],
               'ComplianceType':         evaluation["compliance_type"],
               'Annotation':             evaluation["annotation"],
               'OrderingTimestamp':      invoking_event['configurationItem']['configurationItemCaptureTime']
           },
       ],
       ResultToken=event['resultToken'])
