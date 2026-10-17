# The build image: ONE pin, digest plus the dated release tag it came from (ROADMAP P0.2). The
# tag names the Zephyr branch the ZMK base runs on (config/west.yml: refil/zmk adv360-z3.5-2 is
# Zephyr 3.5) and the SDK (0.16.3). The two CI jobs in .github/workflows/build.yml repeat it
# because a job container cannot read a file; tools/check_image_pin.py fails if they drift.
FROM docker.io/zmkfirmware/zmk-build-arm:3.5-branch-20250930025731-3.5.0-0.16.3-f93290b3ab1a-18117245422@sha256:840526f03c19c286b614d5cb97b11242ae19e468fc2ef2f095f6cf0465fa1c5b

WORKDIR /app

COPY config/west.yml config/west.yml

# West Init
RUN west init -l config
# West Update
RUN west update
# West Zephyr export
RUN west zephyr-export

COPY bin/build.sh ./

CMD ["./build.sh"]
