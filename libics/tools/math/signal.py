import numpy as np
from scipy import signal

from libics.env import logging
from libics.core.data.arrays import ArrayData
from libics.core.util import misc
from libics.tools.math.models import ModelBase
from libics.tools.math.peaked import FitGaussian1d, FitLorentzian1dAbs
from libics.tools import plot


###############################################################################
# Peak detection
###############################################################################


LOGGER_PEAKS = logging.get_logger("libics.tools.math.signal.peaks")


def find_peaks_1d(
    data, npeaks=None, rel_prominence=0.55, check_npeaks=True,
    edge_peaks=False, fit_algorithm="gaussian", ret_vals=None, _DEBUG=False
):
    """
    Finds the peaks of a 1D array by peak prominence.

    Parameters
    ----------
    data : `Array[1, float]`
        1D data to find peaks in.
    npeaks : `int` or `None`
        Number of peaks to be found.
        If `None`, determines `npeaks` from `rel_prominence`.
    rel_prominence : `float`
        Minimum relative prominence of peak w.r.t. mean of other found peaks.
    check_npeaks : `bool` or `str`
        If `npeaks` is given, checks that `npeaks` equals the number of peaks
        found by `rel_prominence`. Performs the following actions if unequal:
        If `error`, raises `RuntimeError`.
        If `warning` or `True`, prints a warning.
        If `False`, does not perform the check.
    edge_peaks : `bool`
        Whether to allow the array edge to be considered as peak.
    fit_algorithm : `str` or `type(ModelBase)`
        Which algorithm to use for peak fitting among:
        `"mean", "gaussian", "lorentzian"`.
        Alternatively, a model class can be given. It must be subclassed
        from `libics.tools.models.ModelBase`; its center parameter must be
        called `x0`, its width `wx`.
    ret_vals : `Iter[str]`
        Sets which values to return. Available options:
        `"width", "fit"`.

    Returns
    -------
    result : `dict(str->list(float))`
        Dictionary containing the following items:
    center, center_err
        Peak positions and uncertainties.
    width
        Peak width.
    """
    # Parse parameters
    ret_vals = set(misc.assume_iter(ret_vals))
    result = {"center": [], "center_err": []}
    if "width" in ret_vals:
        result["width"] = []
    if "fit" in ret_vals:
        if fit_algorithm == "mean":
            raise ValueError("Cannot return `fit` for algorithm `mean`.")
        result["fit"] = []
    # Find peak slices
    peaks = find_peaks_1d_prominence(
        data, npeaks=npeaks, rel_prominence=rel_prominence,
        check_npeaks=check_npeaks, edge_peaks=edge_peaks
    )
    if _DEBUG:
        plot.plot(data, color="black")
    # Peak by mean
    if fit_algorithm == "mean":
        _prob_min = np.mean([x.min() for x in peaks["data"]])
        for x in peaks["data"]:
            _prob = np.array(x) - _prob_min
            _prob = _prob / _prob.sum()
            _mean = (_prob * x.get_points(0)).sum()
            _std = np.sqrt((_prob * (x.get_points(0) - _mean)**2).sum())
            result["center"].append(_mean)
            result["center_err"].append(_std / np.sqrt(len(x)))
            if "width" in result:
                result["width"].append(_std)
        if _DEBUG:
            for i, _ad in enumerate(peaks["data"]):
                label = f"{i:d}: {peaks['prominence'][i]:.3f}"
                plot.plot(_ad, color=f"C{i:d}", label=label)
    # Peak by fit
    else:
        # Find fit class
        if isinstance(fit_algorithm, ModelBase):
            fit_class = fit_algorithm
        elif fit_algorithm == "gaussian":
            fit_class = FitGaussian1d
        elif fit_algorithm == "lorentzian":
            fit_class = FitLorentzian1dAbs
        else:
            raise ValueError(f"Invalid fit_algorithm ({str(fit_algorithm)})")
        # Perform fit
        fits = []
        for _ad in peaks["data"]:
            _fit = fit_class()
            _fit.find_p0(_ad)
            try:
                _fit.find_popt(_ad)
            except TypeError:
                _fit.find_p0(_ad)
                _fit.set_pfit(const=["c"])
                _fit.find_popt(_ad)
            if _fit.psuccess:
                fits.append(_fit)
            else:
                fits.append(None)
        if _DEBUG:
            for i, _ad in enumerate(peaks["data"]):
                _fit = fits[i]
                if _fit is not None:
                    _xcont = _ad.get_points(0)
                    _xcont = np.linspace(_xcont.min(), _xcont.max(), num=256)
                    label = f"{i:d}: {peaks['prominence'][i]:.3f}"
                    plot.plot(
                        _xcont, _fit(_xcont), color=f"C{i:d}", label=label
                    )
        # Get peaks from fits
        for _fit in fits:
            if _fit is not None:
                result["center"].append(_fit.x0)
                result["center_err"].append(_fit.x0_std)
                if "width" in result:
                    result["width"].append(_fit.wx)
                if "fit" in result:
                    result["fit"].append(_fit)
    if _DEBUG:
        ylim = plot.ylim()
        for i, (_c, _e) in enumerate(
            zip(result["center"], result["center_err"])
        ):
            color = f"C{i:d}"
            plot.axvline(_c, color=color)
            plot.fill_between([_c-_e, _c+_e], *ylim, color=color, alpha=0.2)
        plot.ylim(*ylim)
    return result


def find_peaks_1d_prominence(
    data, npeaks=None, rel_prominence=0.55, check_npeaks="warning",
    edge_peaks=False
):
    """
    Finds positive peaks in 1D data by peak prominence.

    Parameters
    ----------
    data : `Array[1, float]`
        1D data to find peaks in.
    npeaks : `int` or `None`
        Number of peaks to be found.
        If `None`, determines `npeaks` from `rel_prominence`.
    rel_prominence : `float`
        Minimum relative prominence of peak w.r.t. mean of other found peaks.
    check_npeaks : `bool` or `str`
        If `npeaks` is given, checks that `npeaks` equals the number of peaks
        found by `rel_prominence`. Performs the following actions if unequal:
        If `error`, raises `RuntimeError`.
        If `warning` or `True`, prints a warning.
        If `False`, does not perform the check.
    edge_peaks : `bool`
        Whether to allow the array edge to be considered as peak.

    Returns
    -------
    ret : `dict(str->Array[1, Any])`
        Dictionary containing the following items:
    position : `np.ndarray(1, float)`
        Raw position of each peak.
    data : `list(ArrayData)`
        List of sliced data containing the data of each peak.
    prominence : `np.ndarray(1, float)`
        Prominence of each peak.

    Note
    ----
    The number of returned peaks may vary.
    """
    ad = ArrayData(data)
    # Find raw peaks
    ar = ad.data.copy()
    if edge_peaks:
        raise NotImplementedError
        ar = np.concatenate([
            # [ar[0] - abs(ar[0]*1e-20)], ar, [ar[-1] - abs(ar[-1]*1e-20)]
            [ar.min()], ar, [ar.min()]
        ])
    _peaks, _props = signal.find_peaks(ar, prominence=0)
    if edge_peaks:
        for _ar in [_peaks, _props["left_bases"], _props["right_bases"]]:
            _numpy_array_shift_inplace(_ar, -1, min=0, max=len(ad) - 1)
    # Sort peaks by prominence
    _order = np.flip(np.argsort(_props["prominences"]))
    peaks, prominences, = _peaks[_order], _props["prominences"][_order]
    lb, rb = _props["left_bases"][_order], _props["right_bases"][_order]
    # Filter for requested peaks
    if npeaks is None or check_npeaks is not False:
        _npeaks = 1
        for i in range(_npeaks, len(peaks)):
            if prominences[i] >= rel_prominence * np.mean(prominences[:i]):
                _npeaks += 1
            else:
                break
        if npeaks is None:
            npeaks = _npeaks
        else:
            if _npeaks != npeaks:
                _msg = (
                    f"Expected `npeaks`={npeaks:d}, "
                    f"but found {_npeaks:d} peaks for "
                    f"`rel_prominence`={rel_prominence:.2f}"
                )
                if check_npeaks == "error":
                    raise RuntimeError(_msg)
                else:
                    LOGGER_PEAKS.warning(_msg)
    # Package data
    return {
        "position": np.array([
            ad.get_points(0)[idx] for idx in peaks[:npeaks]
        ]),
        "data": [ad[lb:rb+1] for lb, rb in zip(lb[:npeaks], rb[:npeaks])],
        "prominence": np.array(prominences[:npeaks])
    }


def _numpy_array_shift_inplace(ar, shift, min=None, max=None):
    ar += shift
    if min:
        ar[ar < min] = min
    if max:
        ar[ar > max] = max


###############################################################################
# Correlation
###############################################################################


def correlate_g2(
    d1, d2, connected=False, normalized=False, mode="valid", method="auto"
):
    """
    Calculates a multidimensional two-point cross-correlation.

    Parameters
    ----------
    d1, d2 : `Arraylike`
        Input arrays.
    connected : `bool`
        Whether to calculate connected correlation (E[x,y]-E[x]E[y]).
    norm : `bool`
        Whether to calculate normalized correlation (E[x,y]/E[x]E[y]).
    mode : `str`
        `"valid", "full", "same"`.
    method : `str`
        `"direct", "fft", "auto"`.

    Returns
    -------
    dc : `Arraylike`
        Correlation array of the same data type as the input arrays.
    """
    # Parse data
    is_ad1 = isinstance(d1, ArrayData)
    is_ad2 = isinstance(d2, ArrayData)
    ar1 = d1.data if is_ad1 else np.array(d1)
    ar2 = d2.data if is_ad2 else np.array(d2)
    ndim = ar1.ndim
    if ndim != ar2.ndim:
        raise ValueError("data dimensions do not agree")
    # Calculate correlation
    arc = signal.correlate(ar1, ar2, mode=mode, method=method)
    arc /= np.prod(
        np.max([np.array(ar1.shape) - 1, np.array(ar2.shape) - 1], axis=0)
    )
    if connected or normalized:
        # Calculate mean
        arm = ar1.mean() * ar2.mean()
        if connected:
            arc = arc - arm
        if normalized:
            res = np.zeros_like(arc, dtype=float)
            np.divide(arc, arm, out=res, where=(arm != 0))
            arc = res
    # Calculate metadata
    if is_ad1 and is_ad2:
        dc = ArrayData(arc)
        # Set data quantity
        d1q, d2q = d1.data_quantity, d2.data_quantity
        if d1q == d2q:
            qn = "correlation"
            if d1q.name != "N/A":
                qn = f"{d1q.name} {qn}"
            if d1q.unit is None:
                qu = None
            else:
                qu = f"{d1q.unit}²"
        else:
            qn = f"{d1q.name}-{d2q.name} correlation"
            qu = None
        if d1q.symbol is None or d2q.symbol is None:
            qs = None
        else:
            qs = f"\\left< {d1q.symbol}_{{i}} {d2q.symbol}_{{i+d}} \\right>"
            mean_s = (
                f"\\left< {d1q.symbol}_i \\right> "
                f"\\left< {d2q.symbol}_i \\right>"
            )
            if np.logical_xor(connected, normalized):
                qs += " - " if connected else " / "
                qs += mean_s
            elif connected and normalized:
                qs = f"({qs} / {mean_s}) - 1"
        dc.set_data_quantity(name=qn, symbol=qs, unit=qu)
        # Set var quantity
        v1q, v2q = d1.var_quantity, d2.var_quantity
        for dim in range(dc.ndim):
            if v1q[dim] == v2q[dim]:
                dc.set_var_quantity(dim, quantity=v1q[dim])
        # Set var points
        for dim in range(dc.ndim):
            offset = d1.get_offset(dim) - d2.get_offset(dim)
            step = d1.get_step(dim)
            if np.isclose(step, d2.get_step(dim)):
                dc.set_dim(dim, offset=offset, step=step)
    else:
        dc = arc
    return dc
