import os
import boto3
import mailparser
import json
import string
import sys
import numpy as np

from hashlib import md5

SOURCE_MAIL = 'shivang@shbharad.com'
EMAIL_MESSAGE = "We received your email sent at {} with the subject {}.\nHere is a 240 character sample of the email body: {}\nThe email was categorized as {} with a {}% confidence.”"

if sys.version_info < (3,):
    maketrans = string.maketrans
else:
    maketrans = str.maketrans
    
def vectorize_sequences(sequences, vocabulary_length):
    results = np.zeros((len(sequences), vocabulary_length))
    for i, sequence in enumerate(sequences):
       results[i, sequence] = 1. 
    return results

def one_hot_encode(messages, vocabulary_length):
    data = []
    for msg in messages:
        temp = one_hot(msg, vocabulary_length)
        data.append(temp)
    return data

def text_to_word_sequence(text, filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n', lower=True, split=" "):
    if lower:
        text = text.lower()

    if sys.version_info < (3,):
        if isinstance(text, unicode):
            translate_map = dict((ord(c), unicode(split)) for c in filters)
            text = text.translate(translate_map)
        elif len(split) == 1:
            translate_map = maketrans(filters, split * len(filters))
            text = text.translate(translate_map)
        else:
            for c in filters:
                text = text.replace(c, split)
    else:
        translate_dict = dict((c, split) for c in filters)
        translate_map = maketrans(translate_dict)
        text = text.translate(translate_map)

    seq = text.split(split)
    return [i for i in seq if i]

def one_hot(text, n, filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n', lower=True, split=' '):
    return hashing_trick(text, n,
                         hash_function='md5',
                         filters=filters,
                         lower=lower,
                         split=split)


def hashing_trick(text, n, hash_function=None, filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n', lower=True, split=' '):
    if hash_function is None:
        hash_function = hash
    elif hash_function == 'md5':
        hash_function = lambda w: int(md5(w.encode()).hexdigest(), 16)

    seq = text_to_word_sequence(text,
                                filters=filters,
                                lower=lower,
                                split=split)
    return [int(hash_function(w) % (n - 1) + 1) for w in seq]

def lambda_handler(event, context):
    try:
        mail_client = boto3.client('ses', region_name='us-east-1')
        s3_client = boto3.client('s3')
        runtime = boto3.Session().client('sagemaker-runtime')
        
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            file = s3_client.get_object(Bucket=bucket, Key=key)
            print("Bucket: {} | Key: {}".format(bucket, key))
            
            byte_mail = file['Body'].read()
            mail = mailparser.parse_from_bytes(byte_mail)
            body = mail.body
            date = mail.date
            email = mail.from_[0][1]
            subject = mail.subject
            
            test_messages = [body.strip()]
            one_hot_test_messages = one_hot_encode(test_messages, 9013)
            encoded_test_messages = vectorize_sequences(one_hot_test_messages, 9013)
            data = json.dumps(encoded_test_messages.tolist())
        
            result = runtime.invoke_endpoint(EndpointName=os.environ['SAGEMAKER_ENDPOINT'], ContentType='application/json', Body=data)
            response = result['Body'].read().decode()
            response = json.loads(response)
        
            label = 'SPAM' if response['predicted_label'][0][0] == 1.0 else 'HAM'
            score = response['predicted_probability'][0][0] if label == 'SPAM' else 1-response['predicted_probability'][0][0]
            
            message = EMAIL_MESSAGE.format(date, subject, body[:240], label, score * 100)
            print("Sending the following message to: {}".format(email))
            print("Message: {}".format(message))
            response = mail_client.send_email(
                Source=SOURCE_MAIL,
                Destination={
                    'ToAddresses': [email],
                    'CcAddresses': [],
                    'BccAddresses': []
                },
                Message={
                    'Subject': {
                        'Data': 'Classification Results of Mail',
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': message,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )
            
        return {
            'statusCode': 200,
            'message': str(response)
        }
    except Exception as e:
        print("Failed with Exception: {}".format(str(e)))
        return {
            'statusCode': 500,
            'message': str(e)
        }
