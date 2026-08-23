import json
import os
import uuid
from datetime import datetime, timezone

import boto3
import redis
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

db = SQLAlchemy()


class Submission(db.Model):
    __tablename__ = "submissions"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name = db.Column(
        db.String(100),
        nullable=False,
    )
    address = db.Column(
        db.String(250),
        nullable=False,
    )
    age = db.Column(
        db.Integer,
        nullable=False,
    )
    archive_status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )


def create_app(config=None):
    app = Flask(__name__)

    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL",
            "sqlite:///:memory:",
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        S3_BUCKET=os.getenv("S3_BUCKET", ""),
        S3_KMS_KEY_ARN=os.getenv("S3_KMS_KEY_ARN", ""),
        AWS_REGION=os.getenv("AWS_REGION", "us-east-1"),
        REDIS_URL=os.getenv("REDIS_URL", ""),
    )

    if config:
        app.config.update(config)

    db.init_app(app)

    @app.get("/health")
    def health():
        try:
            db.session.execute(db.text("SELECT 1"))
            return jsonify(status="healthy"), 200
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Database health check failed")
            return jsonify(status="unhealthy"), 503

    @app.post("/api/submissions")
    def submit():
        payload = (
            request.get_json(silent=True)
            if request.is_json
            else request.form
        )

        if payload is None:
            return jsonify(
                errors=["A valid request body is required."]
            ), 400

        name = str(payload.get("name", "")).strip()
        address = str(payload.get("address", "")).strip()

        try:
            age = int(payload.get("age", ""))
        except (TypeError, ValueError):
            age = -1

        errors = []

        if not 1 <= len(name) <= 100:
            errors.append(
                "Name must contain 1 to 100 characters."
            )

        if not 5 <= len(address) <= 250:
            errors.append(
                "Address must contain 5 to 250 characters."
            )

        if not 0 <= age <= 120:
            errors.append(
                "Age must be between 0 and 120."
            )

        if errors:
            return jsonify(errors=errors), 400

        now = datetime.now(timezone.utc)

        record = Submission(
            name=name,
            address=address,
            age=age,
            archive_status="pending",
            created_at=now,
        )

        try:
            db.session.add(record)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Failed to save submission")
            return jsonify(
                error="The submission could not be saved."
            ), 500

        record_id = str(record.id)

        document = {
            "id": record_id,
            "name": record.name,
            "address": record.address,
            "age": record.age,
            "created_at": now.isoformat(),
        }

        if app.config["S3_BUCKET"]:
            try:
                s3_client = boto3.client(
                    "s3",
                    region_name=app.config["AWS_REGION"],
                )

                s3_request = {
                    "Bucket": app.config["S3_BUCKET"],
                    "Key": (
                        f"submissions/{now:%Y/%m/%d}/"
                        f"{record_id}.json"
                    ),
                    "Body": json.dumps(document).encode("utf-8"),
                    "ContentType": "application/json",
                    "ServerSideEncryption": "aws:kms",
                }

                if app.config["S3_KMS_KEY_ARN"]:
                    s3_request["SSEKMSKeyId"] = app.config[
                        "S3_KMS_KEY_ARN"
                    ]

                s3_client.put_object(**s3_request)
                record.archive_status = "archived"
            except Exception:
                app.logger.exception(
                    "S3 archival failed for %s",
                    record_id,
                )
                record.archive_status = "pending"
        else:
            record.archive_status = "not_configured"

        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception(
                "Failed to update archive status for %s",
                record_id,
            )

        if app.config["REDIS_URL"]:
            try:
                redis_client = redis.from_url(
                    app.config["REDIS_URL"],
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
                redis_client.incr("submission_count")
            except redis.RedisError:
                app.logger.exception(
                    "Redis metric update failed for %s",
                    record_id,
                )

        return jsonify(
            id=record_id,
            archive_status=record.archive_status,
        ), 201

    return app


app = create_app()