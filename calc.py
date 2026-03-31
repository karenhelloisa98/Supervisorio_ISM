import math
import numpy as np

DARCY_M2 = 9.869233e-13
MILLI_DARCY_M2 = 9.869233e-16


def bulk_volume_cylinder(d_m: float, L_m: float) -> float:
    return math.pi * (d_m / 2.0) ** 2 * L_m


def porosity_from_p1_p2(
    p1_pa: float,
    p2_pa: float,
    vref_m3: float,
    vcell_empty_m3: float,
    vbulk_m3: float,
) -> dict:
    """
    MODELO (comum): câmara de referência (Vref) pressurizada a P1
    e câmara da amostra inicialmente evacuada. Ao abrir, equaliza em P2.
    Conservação de massa (gás ideal, T constante):
        P1*Vref = P2*(Vref + Vvoid)
      => Vvoid = Vref*(P1/P2 - 1)

    vcell_empty_m3 = volume livre da célula SEM amostra (calibrado).
    Com amostra, o volume livre vira Vvoid.
      => Vgrain = vcell_empty - Vvoid
    Porosidade:
      Vpore = Vbulk - Vgrain
      phi = Vpore / Vbulk
    """
    if p2_pa <= 0:
        raise ValueError("P2 inválida (<=0).")
    if p1_pa <= 0:
        raise ValueError("P1 inválida (<=0).")
    if p1_pa <= p2_pa:
        raise ValueError("Para este modelo, precisa P1 > P2.")
    if vref_m3 <= 0 or vcell_empty_m3 <= 0 or vbulk_m3 <= 0:
        raise ValueError("Volumes devem ser > 0.")

    vvoid = vref_m3 * (p1_pa / p2_pa - 1.0)  # volume livre com a amostra
    vgrain = vcell_empty_m3 - vvoid
    vpore = vbulk_m3 - vgrain
    phi = vpore / vbulk_m3

    return {
        "Vvoid_m3": float(vvoid),
        "Vgrain_m3": float(vgrain),
        "Vpore_m3": float(vpore),
        "phi": float(phi),
        "phi_percent": float(phi * 100.0),
    }


def estimate_alpha_from_decay(t_s: np.ndarray, dP_pa: np.ndarray) -> float:
    """
    Ajusta ln(dP) = ln(dP0) - alpha*t  -> alpha = -slope
    """
    mask = dP_pa > 0
    t = t_s[mask]
    y = np.log(dP_pa[mask])

    if len(t) < 20:
        raise ValueError("Poucos pontos para estimar alpha (mínimo ~20).")

    slope, _ = np.polyfit(t, y, 1)
    alpha = -slope
    if alpha <= 0:
        raise ValueError("Alpha estimado <= 0 (decay ruim ou dados inconsistentes).")
    return float(alpha)


def permeability_pulse_decay(
    alpha_1_s: float,
    mu_pa_s: float,
    L_m: float,
    A_m2: float,
    Pm_pa: float,
    Vu_m3: float,
    Vd_m3: float,
) -> dict:
    """
    Modelo linearizado (gás ideal, pequena ΔP):
      d(ΔP)/dt = - alpha * ΔP
      alpha = Pm * (k*A/(mu*L)) * (1/Vu + 1/Vd)

    => k = alpha * mu * L / (A * Pm * (1/Vu + 1/Vd))

    Retorna k em m² e em mD.
    """
    if any(x <= 0 for x in [alpha_1_s, mu_pa_s, L_m, A_m2, Pm_pa, Vu_m3, Vd_m3]):
        raise ValueError("Parâmetros inválidos (precisam ser > 0).")

    denom = A_m2 * Pm_pa * (1.0 / Vu_m3 + 1.0 / Vd_m3)
    k_m2 = alpha_1_s * mu_pa_s * L_m / denom
    k_mD = k_m2 / MILLI_DARCY_M2

    return {"k_m2": float(k_m2), "k_mD": float(k_mD)}