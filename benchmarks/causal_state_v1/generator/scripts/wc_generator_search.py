"""Provenance of engine.WC_BASE: the Wilson-Cowan (voltage form, bias-balanced) generator pair used as the nuisance rhythm.
A random search (seeded) kept parameter sets that are quiescent at u = 0 and oscillate at 7-17 Hz for u in {0.6, 1.0, 1.4}; the
chosen set (c253) has a Hopf onset near u = 0.38, 11-13 Hz at the nominal input and an amplitude that grows with u.
    ./sbx python scripts/wc_generator_search.py
"""
import numpy as np
from scipy.integrate import solve_ivp
def sig(v, th, s): return 1/(1+np.exp(-(v-th)/s))
def run(p, u, T=2.0):
    tE,tI,wEE,wEI,wIE,wII,thE,thI,sE,sI,hE,hI = p
    s0E, s0I = sig(0,thE,sE), sig(0,thI,sI)
    def f(t,y):
        vE,vI=y; aE=sig(vE,thE,sE)-s0E; aI=sig(vI,thI,sI)-s0I
        return [(-vE+wEE*aE-wEI*aI+hE*u)/tE, (-vI+wIE*aE-wII*aI+hI*u)/tI]
    sol=solve_ivp(f,(0,T),[0,0],max_step=5e-4,t_eval=np.arange(0,T,1e-3),rtol=1e-7,atol=1e-9)
    x=sig(sol.y[0],thE,sE); x=x[len(x)//2:]
    amp=x.max()-x.min()
    if amp<1e-3: return 0.0, amp
    xc=x-x.mean(); n=len(xc)*8; f_=np.fft.rfftfreq(n,1e-3); P=np.abs(np.fft.rfft(xc,n))**2
    return f_[np.argmax(P[1:])+1], amp


if __name__ == "__main__":
    p = (0.0195, 0.0277, 8.4525, 13.5427, 10.2905, 1.8198, 2.7492, 5.1362, 0.8522, 1.4693, 4.6745, 2.2883)
    for u in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.4, 1.7, 2.1, 3.0):
        f, a = run(p, u, 3.0)
        print(f"u={u:.1f} f={f:5.1f} Hz amp={a:.3f}")
