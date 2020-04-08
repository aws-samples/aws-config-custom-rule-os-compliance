**OS Compliance as a Config rule with Systems Manager integration**

AWS announced that AWS Systems Manager&#39;s &quot;Run Command&quot; now offers Chef InSpec audits through AWS-RunInspecChecks document. This is a big win for the Systems Manager enthusiasts and other users who may not have been completely satisfied with the AWS Inspector.  While AWS Inspector performs thorough audits, provides a very reliable service and a wonderful pipeline integration with the available APIs, the additional configuration tasks like setting up the scan targets and/or the templates, as well as the longer execution times may discourage some users from fully leveraging the service.

This article is not about replacing AWS Inspector nor is it about how to keep an OS compliant but it is about giving AWS customers more cost friendly choice, while encouraging wider adoption of the AWS Config by creating a custom rule that our users can use to monitor their instances.  There already is a [blog](https://aws.amazon.com/blogs/mt/using-aws-systems-manager-to-run-compliance-scans-using-inspec-by-chef/) regarding how to execute Chef InSpec audits via AWS-RunInspecChecks SSM document thus this article focuses on how to set it up as a custom Config rule that checks the CIS compliance.

**A Brief background of Chef InSpec and compliance profiles**

[Chef InSpec](https://www.inspec.io/) is an open source framework for testing and validating applications and infrastructure configuration.  It is based on Ruby&#39;s Spec Suite but InSpec comes with its own DSL (Domain Specific Language).  From all the features of the InSpec, one important thing to highlight, for this article, is the term &quot;compliance profile&quot;.  A &quot;compliance profile&quot; in Chef InSpec refers to a set of &quot;controls&quot;, in which the controls describe the desired state of the application or the infrastructure such as proper owners/group/permissions for files, directories, etc.  All Chef InSpec audits are performed using one or more of these compliance profiles and while the InSpec provides the framework, the &quot;compliance profiles&quot; are the core contents of the compliance audit.  This is important to understand since all audits must run against a standard which can be read and understood by an audit process.  While it is possible for someone to write a brand-new compliance profile for CIS OS audits but it is far better to leverage the existing ones.  For this article, we will be using dev-sec maintained CIS DIL (Distribution Independent Linux) profile written for Chef InSpec audit which is publicly available via [a github repository](https://github.com/dev-sec/cis-dil-benchmark).

**Solution Architecture**

The following diagram illustrates the architecture of the solution

![](./images/ChefInSpecConfigRule.png)

A custom Config rule uses Lambda as its backend.  This solution uses the combination of the lambda function and Systems Manager to perform Operating System level CIS compliance audit.  For this article, we will be using publicly available Chef InSpec compliance profile available in github.  In particular, we will be using [cis-dil](https://github.com/dev-sec/cis-dil-benchmark) (CIS Distribution Independent Linux) benchmark auditing.

**Implementation**

For an automated implementation of the custom Config rule, please use [this Cloudformation template](https://github.com/awsandrewpark/config-rule-inspec-cis-audit-lambda/blob/master/config-rule-inspec-cis-audit-lambda.template) or click on the following link to start the creation of the Cloudformation stack:

[Launch Stack](https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/new?stackName=config-rule-inspec-cis-compliance&templateURL=https://blogpost-staging.s3.amazonaws.com/config-rule-inspec-cis-audit-lambda.template)

Below is the breakdown of the implementation guide.  Overall, the stack performs 5 different tasks:

1. Create an IAM role for the backend lambda
2. Create a lambda function with the provided code
3. Create a new instance profile role for EC2 instances that trusts the lambda
4. Apply the newly created instance profile to the existing EC2 instances
5. Create the custom Config rule

## Create an IAM role for the backend lambda

For any custom AWS Config rule, there has to be a backend lambda and it is the lambda function that performs the compliance determination.  For this solution&#39;s lambda function, the following is the required permissions for the role:

- AmazonEC2FullAccess
- AmazonSSMFullAccess
- AWSLambdaExecute
- AWSConfigRulesExecutionRole

The Cloudformation creates an IAM role named &quot;_IAMRoleForcis-compliance-with-chef-inspec_&quot;, in which these IAM policies are attached.

## Create a lambda function with the provided code

The lambda function code is available [here](https://github.com/awsandrewpark/config-rule-inspec-cis-audit-lambda/blob/master/CisScanningLambda.py) (python 3).  Please note that the code is embedded into the Cloudformation template under the lambda function.  A separate file has been setup for the review purposes only.

## Create a new IAM role for the EC2 instances that trusts the lambda  

In order for the Lambda to be able to execute SSM document, EC2 instances must give the lambda function permission to execute commands on it.  This is achieved by applying the new EC2 instance profiles and establish trust relationship between the instances and the lambda function.

In the &quot;Trust relationships&quot; tab of the IAM instance profile role, ensure that the ARN of the IAM role assigned to the lambda function is specified.  In JSON format, it might look like the following:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/chefInSpecScanLambda",
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

## Create the custom Config rule

A Config rule, at its &quot;fundamental&quot; level, requires the understanding of the following as its building blocks:

- When to trigger the evaluation (Periodic or event driven)
- Where to run the evaluation (such as EC2 instances or S3 buckets, etc)
- What&#39;s my tool to run the evaluation (Integration with other AWS services like Systems Manager or the OS commands)

The Cloudformation template automatically creates the custom Config rule and in brief, the following describes the building blocks:

- **When to trigger the evaluation** : Whenever a change is detected on any EC2 instances.
- **Where to run the evaluation** : Any AWS resources with the following tag ( **Key** : ComplianceBenchmark, **Value** : cis-dil-benchmark).
- **What&#39;s my tool** : Systems Manager Run Command executes AWS-RunInspecChecks document, which in turn, executes Chef InSpec audit with a specific compliance profile.  In our case, the lambda is coded to use cis-dil standard available from the dev-sec&#39;s git repo.

After the Cloudformation has completed provisioning, log into AWS console and open the Config service.  Click on &quot;Rules&quot; and locate the rule name we just created.  Config rule automatically starts the evaluation process after it is created.  If no result is visible, ensure that your EC2 instances are tagged properly as per above ( **Key** : ComplianceBenchmark, **Value** : cis-dil-benchmark) then click &quot;Re-evaluate&quot; to execute the audit again.

## How to access the report

One of the best features about Chef InSpec checks against the Operating Systems is the speed.  For the same CIS scanning, AWS Inspector estimates 1 hour per instance.  Chef InSpec&#39;s cis-dil standard checking takes roughly one minute or less.

One of the areas where Chef InSpec check can improve is the reporting.  Currently, one needs to visit the Systems Manager console and click _Compliance_then click on the EC2 instance ID under Resource pane.  This will bring up a new browser window showing each audit item and the result.  One easy set of filtering one can apply is:

- Compliance type: Equal: Custom:InSpec
- Compliance status: NonCompliant
- Severity: Equal: Critical

This will bring up the urgent topics an administrator must address immediately as seen below:

![ComplianceReportWithFilters](./images/ComplianceReportWithFilters.png)

## Conclusion:

With this article, I have explained what is required for a custom Config rule and I have shown you how to marry an OS compliance with a custom Config rule.  The advantage of having the compliance visibility both in the Systems Manager and AWS Config cannot be under stated and also by integrating with the AWS Config, we have access to the timeline information where we can clearly tell when the instance fell in or out of compliance.

## Related links:

Getting started with custom config rules: [https://docs.aws.amazon.com/config/latest/developerguide/evaluate-config\_develop-rules.html](https://docs.aws.amazon.com/config/latest/developerguide/evaluate-config_develop-rules.html)

AWS Config Rule Development Kit: [https://github.com/awslabs/aws-config-rdk](https://github.com/awslabs/aws-config-rdk) (Caution: this is an open beta product)

Repository of Config rules: [https://github.com/awslabs/aws-config-rules/](https://github.com/awslabs/aws-config-rules/)

Getting Started with Systems Manager: [https://aws.amazon.com/systems-manager/getting-started/](https://aws.amazon.com/systems-manager/getting-started/)

AWS Systems Manager Documentation: [https://docs.aws.amazon.com/systems-manager/index.html#lang/en\_us](https://docs.aws.amazon.com/systems-manager/index.html#lang/en_us)

AWS Systems Manager Development Github Repo: [https://github.com/awslabs/aws-systems-manager](https://github.com/awslabs/aws-systems-manager)

## About the author:

Andrew Park is a Cloud Infrastructure Architect at Amazon Web Services.  With over 20 years of experience as a Linux Systems Administrator and a Cloud Engineer, Andrew is passionate about deep dives into Linux-related challenges, automation and solution development.   He is an open source advocate, dog lover and a hobbyist martial art competitor.
