#include "debug.h"

/* Prepared only: do NOT flash until actual module supply/logic and wiring
 * are confirmed. PB6=SCL, PB7=SDA, open drain, external pull-ups required.
 * This experiment reads identity only; it does not initiate ranging.
 * L0X ID: Linux vl53l0x-i2c.c, reg 0xC0 = 0xEE.
 * L1X ID: ST UM2510 + datasheet, regs 0x010F..0x0110 = 0xEACC.
 * Unknown responses remain unknown; a 0x29 ACK alone is not identification.
 */
#define SCL GPIO_Pin_6
#define SDA GPIO_Pin_7
#define ADDRESS_WRITE 0x52
#define ADDRESS_READ  0x53

/* Visible in GDB even if UART jumper wiring has not been validated. */
volatile uint32_t probe_rounds;
volatile uint32_t probe_kind; /* 0=unknown, 1=L0X, 2=L1X */
volatile uint32_t probe_l0_id;
volatile uint32_t probe_l1_id;
volatile uint32_t probe_l0_error;
volatile uint32_t probe_l1_error;
static uint8_t bus_error; /* 1=SCL stuck, 2=SDA busy, 3=NACK */

static void sda(uint8_t high)
{
    if (high) GPIO_SetBits(GPIOB, SDA); else GPIO_ResetBits(GPIOB, SDA);
    Delay_Us(5);
}
static void scl_low(void)
{
    GPIO_ResetBits(GPIOB, SCL);
    Delay_Us(5);
}
static uint8_t scl_high(void)
{
    unsigned wait;
    GPIO_SetBits(GPIOB, SCL);
    for (wait = 0; wait < 100; ++wait) {
        if (GPIO_ReadInputDataBit(GPIOB, SCL)) { Delay_Us(5); return 1; }
        Delay_Us(5);
    }
    bus_error = 1;
    return 0;
}
static uint8_t start(void)
{
    sda(1);
    if (!scl_high()) return 0;
    if (!GPIO_ReadInputDataBit(GPIOB, SDA)) { bus_error = 2; return 0; }
    sda(0);
    scl_low();
    return 1;
}
static void stop(void)
{
    scl_low();
    sda(0);
    scl_high();
    sda(1);
    GPIO_SetBits(GPIOB, SCL | SDA);
}
static uint8_t write_byte(uint8_t byte)
{
    uint8_t mask;
    for (mask = 0x80; mask; mask >>= 1) {
        sda((byte & mask) != 0);
        if (!scl_high()) return 0;
        scl_low();
    }
    sda(1);
    if (!scl_high()) return 0;
    if (GPIO_ReadInputDataBit(GPIOB, SDA)) bus_error = 3;
    scl_low();
    return bus_error == 0;
}
static uint8_t read_byte(uint8_t *value, uint8_t acknowledge)
{
    uint8_t bit, byte = 0;
    sda(1);
    for (bit = 0; bit < 8; ++bit) {
        if (!scl_high()) return 0;
        byte = (uint8_t)((byte << 1) | GPIO_ReadInputDataBit(GPIOB, SDA));
        scl_low();
    }
    sda(!acknowledge);
    if (!scl_high()) return 0;
    scl_low();
    sda(1);
    *value = byte;
    return 1;
}
static uint8_t read_register(uint16_t reg, uint8_t reg_bytes,
                             uint8_t *data, uint8_t length)
{
    uint8_t i;
    bus_error = 0;
    if (!start() || !write_byte(ADDRESS_WRITE)) goto fail;
    if (reg_bytes == 2 && !write_byte((uint8_t)(reg >> 8))) goto fail;
    if (!write_byte((uint8_t)reg) || !start() || !write_byte(ADDRESS_READ)) goto fail;
    for (i = 0; i < length; ++i)
        if (!read_byte(&data[i], i+1 < length)) goto fail;
    stop();
    return bus_error == 0;
fail:
    stop();
    return 0;
}

int main(void)
{
    GPIO_InitTypeDef gpio = {0};
    uint8_t l0, l1[2];
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);
    SystemCoreClockUpdate();
    Delay_Init();
    USART_Printf_Init(115200);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB | RCC_APB2Periph_GPIOD, ENABLE);
    GPIO_SetBits(GPIOB, SCL | SDA);
    gpio.GPIO_Pin = SCL | SDA;
    gpio.GPIO_Mode = GPIO_Mode_Out_OD;
    gpio.GPIO_Speed = GPIO_Speed_2MHz;
    GPIO_Init(GPIOB, &gpio);
    gpio.GPIO_Pin = GPIO_Pin_0;
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_Init(GPIOD, &gpio);
    Delay_Ms(100);
    printf("ZHIXING R1 SENSOR ID ONLY v1\r\n");
    for (;;) {
        probe_kind = 0;
        probe_l0_id = probe_l1_id = 0xFFFFFFFFu;
        if (read_register(0xC0, 1, &l0, 1)) {
            probe_l0_id = l0;
            if (l0 == 0xEE) probe_kind = 1;
        }
        probe_l0_error = bus_error;
        probe_l1_error = 0;
        if (!probe_kind) {
            if (read_register(0x010F, 2, l1, 2)) {
                probe_l1_id = ((uint16_t)l1[0] << 8) | l1[1];
                if (probe_l1_id == 0xEACC) probe_kind = 2;
            }
            probe_l1_error = bus_error;
        }
        ++probe_rounds;
        printf("ID round=%lu kind=%lu l0=%08lx l1=%08lx err=%lu/%lu\r\n",
               (unsigned long)probe_rounds, (unsigned long)probe_kind,
               (unsigned long)probe_l0_id, (unsigned long)probe_l1_id,
               (unsigned long)probe_l0_error, (unsigned long)probe_l1_error);
        GPIO_SetBits(GPIOD, GPIO_Pin_0);
        Delay_Ms(500);
        GPIO_ResetBits(GPIOD, GPIO_Pin_0);
        Delay_Ms(500);
    }
}
