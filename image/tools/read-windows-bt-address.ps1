# Read the local radio identity through Windows' Bluetooth APIs. No discovery,
# pairing, power, registry, firmware or device-property writes. Keep output private.
$ErrorActionPreference = 'Stop'
if (-not ('Sp11BluetoothReader' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class Sp11BluetoothReader {
    [StructLayout(LayoutKind.Sequential)]
    struct FindParams { public uint Size; }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct RadioInfo {
        public uint Size;
        public ulong Address;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 248)] public string Name;
        public uint Class;
        public ushort Subversion;
        public ushort Manufacturer;
    }
    [DllImport("bthprops.cpl", SetLastError = true)]
    static extern IntPtr BluetoothFindFirstRadio(ref FindParams p, out IntPtr radio);
    [DllImport("bthprops.cpl", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    static extern bool BluetoothFindNextRadio(IntPtr find, out IntPtr radio);
    [DllImport("bthprops.cpl")]
    static extern uint BluetoothGetRadioInfo(IntPtr radio, ref RadioInfo info);
    [DllImport("bthprops.cpl")]
    [return: MarshalAs(UnmanagedType.Bool)]
    static extern bool BluetoothFindRadioClose(IntPtr find);
    [DllImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    static extern bool CloseHandle(IntPtr handle);

    public static string ReadSingle() {
        var p = new FindParams { Size = (uint)Marshal.SizeOf(typeof(FindParams)) };
        IntPtr radio;
        IntPtr find = BluetoothFindFirstRadio(ref p, out radio);
        if (find == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
        var addresses = new List<ulong>();
        try {
            while (true) {
                try {
                    var info = new RadioInfo { Size = (uint)Marshal.SizeOf(typeof(RadioInfo)) };
                    uint error = BluetoothGetRadioInfo(radio, ref info);
                    if (error != 0) throw new Win32Exception((int)error);
                    addresses.Add(info.Address & 0xFFFFFFFFFFFFUL);
                } finally { CloseHandle(radio); }
                if (!BluetoothFindNextRadio(find, out radio)) {
                    int error = Marshal.GetLastWin32Error();
                    if (error != 259) throw new Win32Exception(error); // ERROR_NO_MORE_ITEMS
                    break;
                }
            }
        } finally { BluetoothFindRadioClose(find); }
        if (addresses.Count != 1) throw new Exception("Expected one local radio; remove external Bluetooth adapters and retry.");
        ulong value = addresses[0];
        if (value == 0 || value == 0xFFFFFFFFFFFFUL || value == 0x5AADUL)
            throw new Exception("Windows returned an unusable address sentinel.");
        string hex = value.ToString("X12");
        var bytes = new string[6];
        for (int i = 0; i < 6; i++) bytes[i] = hex.Substring(i * 2, 2);
        return String.Join(":", bytes);
    }
}
'@
}
[Sp11BluetoothReader]::ReadSingle()
