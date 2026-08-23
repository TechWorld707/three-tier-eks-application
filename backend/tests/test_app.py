import json

import app as application


def create_test_app(tmp_path, **overrides):
    database_path = tmp_path / "test.db"

    config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": (
            f"sqlite:///{database_path}"
        ),
        "S3_BUCKET": "",
        "S3_KMS_KEY_ARN": "",
        "REDIS_URL": "",
    }

    config.update(overrides)

    flask_app = application.create_app(config)

    with flask_app.app_context():
        application.db.create_all()

    return flask_app


def test_health_endpoint_returns_healthy(tmp_path):
    flask_app = create_test_app(tmp_path)

    response = flask_app.test_client().get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "healthy"}


def test_valid_submission_is_saved_and_archived(
    tmp_path,
    monkeypatch,
):
    stored = {}

    class FakeS3Client:
        def put_object(self, **kwargs):
            stored.update(kwargs)

    monkeypatch.setattr(
        application.boto3,
        "client",
        lambda *args, **kwargs: FakeS3Client(),
    )

    flask_app = create_test_app(
        tmp_path,
        S3_BUCKET="test-submission-bucket",
        S3_KMS_KEY_ARN=(
            "arn:aws:kms:us-east-1:123456789012:"
            "key/11111111-2222-3333-4444-555555555555"
        ),
        AWS_REGION="us-east-1",
    )

    response = flask_app.test_client().post(
        "/api/submissions",
        json={
            "name": "Ada",
            "address": "1 Example Road",
            "age": 36,
        },
    )

    assert response.status_code == 201
    assert response.json["archive_status"] == "archived"

    assert stored["Bucket"] == "test-submission-bucket"
    assert stored["ServerSideEncryption"] == "aws:kms"
    assert stored["SSEKMSKeyId"].startswith("arn:aws:kms:")
    assert stored["Key"].startswith("submissions/")
    assert json.loads(stored["Body"])["name"] == "Ada"

    with flask_app.app_context():
        records = application.Submission.query.all()

        assert len(records) == 1
        assert records[0].name == "Ada"
        assert records[0].archive_status == "archived"


def test_invalid_submission_is_rejected(tmp_path):
    flask_app = create_test_app(tmp_path)

    response = flask_app.test_client().post(
        "/api/submissions",
        json={
            "name": "",
            "address": "x",
            "age": 999,
        },
    )

    assert response.status_code == 400
    assert len(response.json["errors"]) == 3