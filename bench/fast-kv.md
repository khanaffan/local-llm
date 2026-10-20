=== KV f16
| model                          |       size |     params | backend    | threads |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | ------: | --: | --------------: | -------------------: |
| gpt-oss 20B MXFP4 MoE          |  11.27 GiB |    20.91 B | BLAS,MTL   |       6 |   1 |           pp512 |       3884.85 ± 7.71 |
| gpt-oss 20B MXFP4 MoE          |  11.27 GiB |    20.91 B | BLAS,MTL   |       6 |   1 |          pp8192 |     3340.01 ± 134.58 |
| gpt-oss 20B MXFP4 MoE          |  11.27 GiB |    20.91 B | BLAS,MTL   |       6 |   1 |         pp30000 |       2230.44 ± 2.30 |
| gpt-oss 20B MXFP4 MoE          |  11.27 GiB |    20.91 B | BLAS,MTL   |       6 |   1 |           tg128 |        150.05 ± 0.69 |
=== KV q8_0
| model                          |       size |     params | backend    | threads | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | ------: | -----: | -----: | --: | --------------: | -------------------: |
| gpt-oss 20B MXFP4 MoE          |  11.27 GiB |    20.91 B | BLAS,MTL   |       6 |   q8_0 |   q8_0 |   1 |           pp512 |      3659.85 ± 55.88 |
| gpt-oss 20B MXFP4 MoE          |  11.27 GiB |    20.91 B | BLAS,MTL   |       6 |   q8_0 |   q8_0 |   1 |          pp8192 |      3153.42 ± 13.70 |
| gpt-oss 20B MXFP4 MoE          |  11.27 GiB |    20.91 B | BLAS,MTL   |       6 |   q8_0 |   q8_0 |   1 |         pp30000 |      2243.36 ± 28.27 |
| gpt-oss 20B MXFP4 MoE          |  11.27 GiB |    20.91 B | BLAS,MTL   |       6 |   q8_0 |   q8_0 |   1 |           tg128 |        145.13 ± 0.17 |
