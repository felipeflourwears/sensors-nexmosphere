# Sensors Nexmosphere

## Serial

### RFDI Flags 
```bash
XR[PB001] --> Puesto en el TAG
XR[PU001] --> Retirar del TAG
```
### ID
```bash
XR[PB001] --> TAG1
XR[PB002] --> TAG2
```

### Magnetic pick-up sensor 
```bash
X003A[3] --> Stand by sensor
X003A[0] --> Pick up sensor
```

### Air Button
```bash
X004B[Bs=NEAR] --> Cerca
X004B[Bs=FAR] --> Lejos
X004B[Bs=IDLE] --> Desactivado o fuera del area
```

### Rotary Button
```bash
Ranges values
X002B[Dr=1] ----- X002B[Dr=20]
```

### Push Buttons
```bash
X001A[17] --> Press Button 1
X001A[3]  --> Press Button 2
X001A[0]  --> Dejar de hacer press en ambos casos
```

### Presence Sensor
```bash

```