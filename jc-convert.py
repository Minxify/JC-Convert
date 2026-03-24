import tkinter as tk
from tkinter import ttk, messagebox
import evdev
from evdev import ecodes, UInput
import threading

class JoyMapperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Arch Joy-Con Master")
        self.root.geometry("450x400")

        self.running = False
        self.ui = None

        # Sensitivity Variable (Default to 10)
        self.sensitivity = tk.IntVar(value=10)

        # UI Elements
        self.status_var = tk.StringVar(value="Status: Ready")
        ttk.Label(root, textvariable=self.status_var, font=("Helvetica", 14, "bold")).pack(pady=10)

        # Slider
        ttk.Label(root, text="Mouse Sensitivity:").pack()
        self.slider = ttk.Scale(root, from_=1, to=50, variable=self.sensitivity, orient="horizontal")
        self.slider.pack(fill="x", padx=40, pady=5)
        ttk.Label(root, textvariable=self.sensitivity).pack()

        self.btn = ttk.Button(root, text="START MAPPING", command=self.toggle)
        self.btn.pack(pady=20)

        # Legend
        info = ttk.LabelFrame(root, text="Current Bindings")
        info.pack(padx=20, pady=10, fill="both")
        ttk.Label(info, text="• R-Stick: Mouse | L-Stick: Scroll").pack(anchor="w", padx=5)
        ttk.Label(info, text="• B/A: LMB/RMB | Home: Super").pack(anchor="w", padx=5)
        ttk.Label(info, text="• X: Vol Up | Y: Vol Down").pack(anchor="w", padx=5)
        ttk.Label(info, text="• -: Mute | Screenshot: PrtSc").pack(anchor="w", padx=5)

    def find_actual_joycons(self):
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        r_joy, l_joy = None, None
        for d in devices:
            caps = d.capabilities()
            if "Joy-Con (R)" in d.name and ecodes.EV_KEY in caps:
                r_joy = d
            elif "Joy-Con (L)" in d.name and ecodes.EV_KEY in caps:
                l_joy = d
        return l_joy, r_joy

    def run_mapping_logic(self, l_dev, r_dev):
        cap = {
            ecodes.EV_KEY: [
                ecodes.BTN_LEFT, ecodes.BTN_RIGHT,
                ecodes.KEY_VOLUMEDOWN, ecodes.KEY_VOLUMEUP,
                ecodes.KEY_F, ecodes.KEY_LEFTMETA,
                ecodes.KEY_MUTE, ecodes.KEY_SYSRQ,
                ecodes.KEY_UP, ecodes.KEY_DOWN, ecodes.KEY_LEFT, ecodes.KEY_RIGHT
            ],
            ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL, ecodes.REL_HWHEEL]
        }

        try:
            self.ui = UInput(cap, name="JoyCon-Mouse-Emulator")
        except:
            self.root.after(0, lambda: messagebox.showerror("Error", "Permissions denied. Run with sudo!"))
            return

        def handle_right():
            for event in r_dev.read_loop():
                if not self.running: break

                if event.type == ecodes.EV_ABS:
                    # Get the current slider value (1-50)
                    # We'll treat 10 as "normal", so we divide by 10 to get a multiplier
                    sens_multiplier = self.sensitivity.get() / 10.0

                    if event.code in [ecodes.ABS_X, ecodes.ABS_RX, ecodes.ABS_HAT0X]:
                        # Normalize: Center is 128, range is usually 0-255
                        val = event.value - 128 if event.code != ecodes.ABS_HAT0X else event.value * 128

                        # DEADZONE: If the tilt is less than 20 units, ignore it
                        if abs(val) > 20:
                            # HEAVY DAMPENING: Divide the raw value by 150 before applying sensitivity
                            move_x = int((val / 150) * sens_multiplier)
                            self.ui.write(ecodes.EV_REL, ecodes.REL_X, move_x)

                    if event.code in [ecodes.ABS_Y, ecodes.ABS_RY, ecodes.ABS_HAT0Y]:
                        val = event.value - 128 if event.code != ecodes.ABS_HAT0Y else event.value * 128

                        if abs(val) > 20:
                            # HEAVY DAMPENING
                            move_y = int((val / 150) * sens_multiplier)
                            self.ui.write(ecodes.EV_REL, ecodes.REL_Y, move_y)

                # ... (Keep the button mapping logic below this) ...
                if event.type == ecodes.EV_KEY:
                    mapping = {
                        ecodes.BTN_SOUTH: ecodes.BTN_LEFT,   # B
                        ecodes.BTN_EAST: ecodes.BTN_RIGHT,   # A
                        ecodes.BTN_NORTH: ecodes.KEY_VOLUMEUP, # X
                        ecodes.BTN_WEST: ecodes.KEY_VOLUMEDOWN, # Y
                        ecodes.BTN_START: ecodes.KEY_F,      # Plus
                        ecodes.BTN_MODE: ecodes.KEY_LEFTMETA # Home
                    }
                    if event.code in mapping:
                        self.ui.write(ecodes.EV_KEY, mapping[event.code], event.value)
                self.ui.syn()

        def handle_left():
            scroll_decelerator = 0
            for event in l_dev.read_loop():
                if not self.running: break

                if event.type == ecodes.EV_ABS:
                    # SCROLLING
                    if event.code in [ecodes.ABS_X, ecodes.ABS_Y]:
                        val = event.value - 128
                        if abs(val) > 30:
                            scroll_decelerator += 1
                            if scroll_decelerator > 20: # Slows scroll speed
                                if event.code == ecodes.ABS_Y:
                                    self.ui.write(ecodes.EV_REL, ecodes.REL_WHEEL, -1 if val > 0 else 1)
                                else:
                                    self.ui.write(ecodes.EV_REL, ecodes.REL_HWHEEL, 1 if val > 0 else -1)
                                scroll_decelerator = 0

                    # D-PAD
                    if event.code == ecodes.ABS_HAT0X:
                        self.ui.write(ecodes.EV_KEY, ecodes.KEY_RIGHT, 1 if event.value == 1 else 0)
                        self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFT, 1 if event.value == -1 else 0)
                    if event.code == ecodes.ABS_HAT0Y:
                        self.ui.write(ecodes.EV_KEY, ecodes.KEY_DOWN, 1 if event.value == 1 else 0)
                        self.ui.write(ecodes.EV_KEY, ecodes.KEY_UP, 1 if event.value == -1 else 0)

                if event.type == ecodes.EV_KEY:
                    if event.code == ecodes.BTN_SELECT: # Minus
                        self.ui.write(ecodes.EV_KEY, ecodes.KEY_MUTE, event.value)
                    if event.code in [0x232, 544]: # Screenshot
                        self.ui.write(ecodes.EV_KEY, ecodes.KEY_SYSRQ, event.value)
                self.ui.syn()

        threading.Thread(target=handle_right, daemon=True).start()
        threading.Thread(target=handle_left, daemon=True).start()

    def toggle(self):
        if not self.running:
            l, r = self.find_actual_joycons()
            if not l or not r:
                messagebox.showwarning("Sync Error", "Joy-Cons not found. Re-pair them in Bluetooth settings!")
                return
            self.running = True
            self.status_var.set("Status: ACTIVE")
            self.btn.config(text="STOP MAPPING")
            self.run_mapping_logic(l, r)
        else:
            self.running = False
            self.status_var.set("Status: Stopped")
            self.btn.config(text="START MAPPING")

if __name__ == "__main__":
    root = tk.Tk()
    app = JoyMapperApp(root)
    root.mainloop()
