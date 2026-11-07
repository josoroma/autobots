# US-14.13, Decision 0018 B3: the egress proxy and CDP gate, standard library only.
# Built locally from services/agent/src/autobots/adapters, on a base pinned by digest.
FROM python@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
COPY egress_proxy.py /app/egress_proxy.py
USER 65534:65534
ENTRYPOINT ["python", "-I", "/app/egress_proxy.py"]
