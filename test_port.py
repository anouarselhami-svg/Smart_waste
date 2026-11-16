import serial, time
ser = serial.serial_for_url("rfc2217://localhost:4000", baudrate=115200, timeout=1)
ser.write(b"PING\n")
time.sleep(1)
print(ser.read(200).decode(errors="replace"))
ser.close()