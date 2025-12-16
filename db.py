import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import boto3
import pymysql


@dataclass
class DbCreds:
  username: str
  password: str
  host: str
  port: int
  dbname: str


_SECRET_CACHE: Optional[Tuple[float, DbCreds]] = None  # (expires_epoch, creds)


def _get_region() -> str:
  return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"


def _load_creds_from_secret() -> DbCreds:
  secret_id = os.environ["DB_SECRET_ID"]
  db_endpoint = os.environ.get("DB_ENDPOINT")  # optional override
  db_name = os.environ.get("DB_NAME")          # optional override

  sm = boto3.client("secretsmanager", region_name=_get_region())
  resp = sm.get_secret_value(SecretId=secret_id)
  payload = resp.get("SecretString") or ""
  data: Dict[str, Any] = json.loads(payload)

  # RDS-managed secrets typically include these keys:
  username = data.get("username") or data.get("user")
  password = data.get("password")
  host = db_endpoint or data.get("host")
  port = int(data.get("port") or 3306)
  dbname = db_name or data.get("dbname") or data.get("database") or ""

  if not all([username, password, host]):
    raise RuntimeError(f"Secret {secret_id} missing required fields (username/password/host).")

  if not dbname:
    raise RuntimeError("DB_NAME not provided and secret does not include dbname.")

  return DbCreds(username=username, password=password, host=host, port=port, dbname=dbname)


def get_db_creds(cache_ttl_seconds: int = 300) -> DbCreds:
  global _SECRET_CACHE
  now = time.time()

  if _SECRET_CACHE is not None:
    expires, creds = _SECRET_CACHE
    if now < expires:
      return creds

  creds = _load_creds_from_secret()
  _SECRET_CACHE = (now + cache_ttl_seconds, creds)
  return creds


def get_conn():
  creds = get_db_creds()
  return pymysql.connect(
    host=creds.host,
    user=creds.username,
    password=creds.password,
    database=creds.dbname,
    port=creds.port,
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=True,
  )
