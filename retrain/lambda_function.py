import os
import boto3

from datetime import datetime

INSTANCE_TYPE = 'ml.m5.large'
NAME_PREFIX = 'sms-spam-classifier-mxnet-{}'

def lambda_handler(event, context):
    print("Event: {}".format(event))
    client = boto3.Session().client('sagemaker')
    date_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]
    if 'source' in event and event['source'] == 'aws.sagemaker':
        if 'detail' not in event:
            return {
                'statusCode': 200,
                'message': 'Training Status change not found in detail'
            }
        
        if 'TrainingJobStatus' not in event['detail'] or 'SecondaryStatus' not in event['detail']:
            return {
                'statusCode': 200,
                'message': 'Training Status change not found in detail'
            }
        
        trainingStatus = event['detail']['TrainingJobStatus']
        secondaryStatus = event['detail']['SecondaryStatus']
        print("Training Status: {} | Secondary Status: {}".format(trainingStatus, secondaryStatus))
        if trainingStatus != 'Completed' or secondaryStatus != 'Completed':
            return {
                'statusCode': 200,
                'message': 'Training Status not completed yet'
            }
        
        print("Creating model resource from training artifact")
        model_artifact = event['detail']['ModelArtifacts']['S3ModelArtifacts']
        training_image = event['detail']['AlgorithmSpecification']['TrainingImage']
        role = event['detail']['RoleArn']
        model_name = NAME_PREFIX.format(date_str)
        print("{} | {} | {} | {}".format(model_name, training_image, model_artifact, role))
        client.create_model(
            ModelName=model_name,
            PrimaryContainer={
                'Image': training_image,
                'ModelDataUrl': model_artifact
            },
            ExecutionRoleArn=role
        )
        
        print("Creating endpoint configuration")
        client.create_endpoint_config(
            EndpointConfigName=model_name,
            ProductionVariants=[
                {
                    'VariantName': 'AllTraffic',
                    'ModelName': model_name,
                    'InitialInstanceCount': 1,
                    'InstanceType': INSTANCE_TYPE
                }
            ]
        )
        
        print("Deploying to endpoint: {}".format(os.environ['SAGEMAKER_ENDPOINT']))
        client.update_endpoint(
            EndpointName=os.environ['SAGEMAKER_ENDPOINT'],
            EndpointConfigName=model_name
        )

        return {
            'statusCode': 200,
            'message': 'Deployment of the model queued'
        }
    
    print("Called by EventBridge")
    training_job_name = NAME_PREFIX.format(date_str)
    response = client.list_training_jobs(StatusEquals='Completed')
    print("Training Jobs: {}".format(response))
    
    job_name = response['TrainingJobSummaries'][0]['TrainingJobName']
    job = client.describe_training_job(TrainingJobName=job_name)
    print("Job: {}".format(job))
    response = client.create_training_job(
        TrainingJobName=training_job_name, 
        AlgorithmSpecification=job['AlgorithmSpecification'], 
        RoleArn=job['RoleArn'],
        InputDataConfig=job['InputDataConfig'], 
        OutputDataConfig=job['OutputDataConfig'],
        ResourceConfig=job['ResourceConfig'], 
        StoppingCondition=job['StoppingCondition'],
        HyperParameters=job['HyperParameters'] if 'HyperParameters' in job else {},
        Tags=job['Tags'] if 'Tags' in job else []
    )

    return {
        'statusCode': 200,
        'message': 'Training job queued'
    }
