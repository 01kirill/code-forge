FROM judge0/judge0:1.13.1
USER root
RUN sed -i 's@sudo tee /api/environment@sudo tee /api/environment >/dev/null@' \
    /api/scripts/server /api/scripts/workers
USER judge0
