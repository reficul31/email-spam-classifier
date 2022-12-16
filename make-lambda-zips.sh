cd retrain
zip retrain-lambda.zip lambda_function.py
mv retrain-lambda.zip ..
cd ../spam-classifier
zip spam-classifier-lambda.zip lambda_function.py
mv spam-classifier-lambda.zip ..
cd ..