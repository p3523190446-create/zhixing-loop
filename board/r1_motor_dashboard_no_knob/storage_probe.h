#ifndef STORAGE_PROBE_H
#define STORAGE_PROBE_H
#include <stdint.h>
extern volatile uint32_t storage_jedec_id,storage_sr1,storage_sr2;
extern volatile uint32_t storage_probes,storage_matches,storage_ready;
uint8_t storage_status(void);
int storage_read(uint32_t address,uint8_t *out,unsigned length);
int storage_program(uint32_t address,const uint8_t *data,unsigned length);
int storage_erase_sector(uint32_t address);
void storage_write_disable(void);
void storage_probe_init(void);
void storage_probe_sample(void);
#endif
