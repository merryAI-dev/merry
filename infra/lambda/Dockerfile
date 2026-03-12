FROM public.ecr.aws/lambda/python:3.11

# Install Python dependencies
# pymupdf pinned to 1.25.5 (last version with manylinux_2_17 pre-built wheel for Lambda AL2)
# Only playground_parser deps needed: fitz(pymupdf), boto3, pillow
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir \
    "pymupdf==1.25.5" \
    boto3 \
    "botocore[crt]" \
    pillow

# Copy ralph package
COPY ralph/ ${LAMBDA_TASK_ROOT}/ralph/

# Copy Lambda handler
COPY infra/lambda/handler.py ${LAMBDA_TASK_ROOT}/handler.py

CMD ["handler.handler"]
