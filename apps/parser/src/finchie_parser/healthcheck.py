"""`python -m finchie_parser.healthcheck`: exit 0 when the local server reports SERVING.

The image has no shell tools, so the container healthcheck needs its own client.
"""

import sys

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc

from finchie_parser.settings import Settings


def main() -> int:
    port = Settings().port
    try:
        with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
            response = health_pb2_grpc.HealthStub(channel).Check(health_pb2.HealthCheckRequest(), timeout=3)
    except grpc.RpcError as error:
        print(f"unhealthy: {error.code().name}", file=sys.stderr)
        return 1
    return 0 if response.status == health_pb2.HealthCheckResponse.SERVING else 1


if __name__ == "__main__":
    sys.exit(main())
