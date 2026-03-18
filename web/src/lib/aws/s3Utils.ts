import { GetObjectCommand } from "@aws-sdk/client-s3";
import { getS3Client } from "@/lib/aws/s3";

/** Read raw bytes from an S3 object. */
export async function readBytesFromS3(s3Key: string, s3Bucket: string): Promise<Buffer> {
  const s3 = getS3Client();
  const res = await s3.send(new GetObjectCommand({ Bucket: s3Bucket, Key: s3Key }));
  const body = res.Body;
  if (!body) throw new Error("S3_EMPTY_BODY");
  const bytes = await body.transformToByteArray();
  return Buffer.from(bytes);
}

/** Read a text file from S3 as UTF-8 string. */
export async function readTextFromS3(s3Key: string, s3Bucket: string): Promise<string> {
  const buffer = await readBytesFromS3(s3Key, s3Bucket);
  return buffer.toString("utf-8");
}
