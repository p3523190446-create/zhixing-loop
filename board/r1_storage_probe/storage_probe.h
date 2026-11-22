#ifndef STORAGE_PROBE_H
#define STORAGE_PROBE_H
#include <stdint.h>
extern volatile uint32_t storage_jedec_id,storage_sr1,storage_sr2;
extern volatile uint32_t storage_probes,storage_matches,storage_ready;
void storage_probe_init(void);
void storage_probe_sample(void);
#endif
