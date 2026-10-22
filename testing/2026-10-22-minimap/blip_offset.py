# The offset of Blizzard's flat minimap blips from GPS's tilted view of the ground at your height, by tilt, lens
# and with or without the screen's up stretched by 1 / sin(elevation) (Minimap.lua's cam.stretch); px on a 198 px minimap.
import math
def err(tilt_deg, fov_deg, stretch, Rpx=99):
    p=math.radians(90-tilt_deg)  # elevation
    fov=math.radians(fov_deg)
    H=Rpx  # canvas half height in px ~ radius
    F=H/math.tan(fov/2)
    R=200.0  # yards across radius (scale free)
    s=Rpx/R
    D=F/s
    f=(0,math.cos(p),-math.sin(p)); r=(1,0,0); u=(0,math.sin(p),math.cos(p))
    k=1/math.sin(p) if stretch else 1
    c=(0-f[0]*D,0-f[1]*D,0-f[2]*D)
    worst=0;w50=0
    for i in range(72):
        a=i*2*math.pi/72
        for rr in (R*0.25,R*0.5,R):
            e,n=rr*math.cos(a),rr*math.sin(a)
            dx,dy,dz=e-c[0],n-c[1],0-c[2]
            d=dx*f[0]+dy*f[1]+dz*f[2]
            sx=(dx*r[0]+dy*r[1])*F/d; sy=k*(dx*u[0]+dy*u[1]+dz*u[2])*F/d
            er=math.hypot(sx-s*e,sy-s*n)
            worst=max(worst,er)
            if rr==R*0.5: w50=max(w50,er)
    return worst,w50,D
for tilt in (20,30,40,45):
    for fov in (50,30,20,10):
        for st in (False,True):
            w,w50,D=err(tilt,fov,st)
            print(f"tilt {tilt} fov {fov} stretch {st}: edge {w:5.1f}px half {w50:5.1f}px camdist {D:6.0f}yd")
