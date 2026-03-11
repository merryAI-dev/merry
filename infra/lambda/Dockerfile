FROM public.ecr.aws/lambda/python:3.11

# PyMuPDF needs these system libraries
RUN dnf install -y gcc gcc-c++ libpng-devel libjpeg-devel freetype-devel && \
    dnf clean all

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir \
    pymupdf \
    boto3 \
    "botocore[crt]" \
    pillow

# Copy ralph package
COPY ralph/ ${LAMBDA_TASK_ROOT}/ralph/

# Copy Lambda handler
COPY infra/lambda/handler.py ${LAMBDA_TASK_ROOT}/handler.py

CMD ["handler.handler"]
