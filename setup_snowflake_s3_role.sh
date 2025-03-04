#!/bin/bash
# Save as setup_snowflake_s3_role.sh

# Variables based on your information
AWS_ACCOUNT_ID="418295715028"
BUCKET_NAME="helius-webhook-418295715028-us-east-1"
SNOWFLAKE_IAM_USER="arn:aws:iam::396913736211:user/c9zw0000-s"
EXTERNAL_ID="BZB54887_SFCRole=5_dFTrZ870IdA5SOo8zPnd5MzUpN4="
ROLE_NAME="snowflake-s3-role"

echo "Creating trust policy JSON file..."
cat > trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "${SNOWFLAKE_IAM_USER}"
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "sts:ExternalId": "${EXTERNAL_ID}"
                }
            }
        }
    ]
}
EOF

echo "Creating S3 access policy JSON file..."
cat > s3-access-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:GetObjectVersion"
            ],
            "Resource": "arn:aws:s3:::${BUCKET_NAME}/processed-data/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation"
            ],
            "Resource": "arn:aws:s3:::${BUCKET_NAME}",
            "Condition": {
                "StringLike": {
                    "s3:prefix": "processed-data/*"
                }
            }
        }
    ]
}
EOF

echo "Creating IAM role ${ROLE_NAME}..."
aws iam create-role \
    --role-name ${ROLE_NAME} \
    --assume-role-policy-document file://trust-policy.json

echo "Creating policy for S3 access..."
POLICY_ARN=$(aws iam create-policy \
    --policy-name SnowflakeS3Access \
    --policy-document file://s3-access-policy.json \
    --query 'Policy.Arn' \
    --output text)

echo "Attaching policy to role..."
aws iam attach-role-policy \
    --role-name ${ROLE_NAME} \
    --policy-arn ${POLICY_ARN}

echo "Role setup complete. Role ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"