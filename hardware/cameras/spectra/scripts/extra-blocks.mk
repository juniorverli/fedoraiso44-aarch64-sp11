# Extra Spectra blocks that CONFIG_X1E80100 does not enable (experiment: do they compile on v7.3?)
CONFIG_SPECTRA_FD := y
ccflags-y += -DCONFIG_SPECTRA_FD=1
CONFIG_SPECTRA_LRME := y
ccflags-y += -DCONFIG_SPECTRA_LRME=1
CONFIG_SPECTRA_CRE := y
ccflags-y += -DCONFIG_SPECTRA_CRE=1
CONFIG_SPECTRA_OPE := y
ccflags-y += -DCONFIG_SPECTRA_OPE=1
CONFIG_SPECTRA_TFE := y
ccflags-y += -DCONFIG_SPECTRA_TFE=1
CONFIG_SPECTRA_CUSTOM := y
ccflags-y += -DCONFIG_SPECTRA_CUSTOM=1
