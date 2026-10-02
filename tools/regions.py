"""The three retail releases of Kirby's Return to Dream Land (Wii)."""
REGIONS = {
    'SUKE01': dict(label="Kirby's Return to Dream Land (USA)", short='USA', version=0),
    'SUKP01': dict(label="Kirby's Adventure Wii (Europe/Australia)", short='Europe', version=0),
    'SUKJ01': dict(label='Hoshi no Kirby Wii (Japan)', short='Japan', version=0),
}

# retail DOL sizes, to give a clear error on someone else's modified dump
DOL_SIZES = {'SUKE01': 8321120, 'SUKP01': 8327648, 'SUKJ01': 8311392}
