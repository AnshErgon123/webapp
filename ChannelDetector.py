import can

configs = can.detect_available_configs()
print("Available CAN configs:")
for cfg in configs:
    print(cfg)
