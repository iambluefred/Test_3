#!/usr/bin/env python3
from cereal import car, arne182, log
from selfdrive.config import Conversions as CV
from selfdrive.car.toyota.values import Ecu, ECU_FINGERPRINT, CAR, TSS2_CAR, FINGERPRINTS
from selfdrive.car import STD_CARGO_KG, scale_rot_inertia, scale_tire_stiffness, is_ecu_disconnected, gen_empty_fingerprint
from selfdrive.swaglog import cloudlog
from selfdrive.car.interfaces import CarInterfaceBase
from common.op_params import opParams

op_params = opParams()
spairrowtuning = op_params.get('spairrowtuning')
corolla_tss2_d_tuning = op_params.get('corolla_tss2_d_tuning')
prius_pid = op_params.get('prius_pid')

GearShifter = car.CarState.GearShifter

LaneChangeState = log.PathPlan.LaneChangeState

EventName = car.CarEvent.EventName
EventNameArne182 = arne182.CarEventArne182.EventNameArne182

class CarInterface(CarInterfaceBase):
  @staticmethod
  def compute_gb(accel, speed):
    return float(accel) / 4.0

  @staticmethod
  def get_params(candidate, fingerprint=gen_empty_fingerprint(), has_relay=False, car_fw=[]):  # pylint: disable=dangerous-default-value
    ret = CarInterfaceBase.get_std_params(candidate, fingerprint, has_relay)

    ret.carName = "toyota"
    ret.safetyModel = car.CarParams.SafetyModel.toyota

    ret.steerActuatorDelay = 0.12  # Default delay, Prius has larger delay
    ret.steerLimitTimer = 0.4

    if ret.enableGasInterceptor:
      ret.gasMaxBP = [0., 9., 55]
      ret.gasMaxV = [0.2, 0.5, 0.7]
      # ret.longitudinalTuning.kpV = [0.5, 0.4, 0.3]  # braking tune, todo: test me vs. stock below
      # ret.longitudinalTuning.kiV = [0.135, 0.1]
      ret.longitudinalTuning.kpV = [1.2, 0.8, 0.5]
      ret.longitudinalTuning.kiV = [0.18, 0.12]
    else:
      ret.gasMaxBP = [0., 9., 55]
      ret.gasMaxV = [0.2, 0.5, 0.7]
      ret.longitudinalTuning.kpV = [0.4, 0.36, 0.325]  # braking tune from rav4h
      ret.longitudinalTuning.kiV = [0.195, 0.10]

    if candidate not in [CAR.PRIUS_2019, CAR.PRIUS, CAR.RAV4, CAR.RAV4H, CAR.RAV4H_TSS2, CAR.COROLLA, CAR.PRIUS_TSS2] and not spairrowtuning: # These cars use LQR/INDI
      ret.lateralTuning.init('pid')
      ret.lateralTuning.pid.kiBP, ret.lateralTuning.pid.kpBP, ret.lateralTuning.pid.kfBP = [[0.], [0.], [0.]]
      ret.lateralTuning.pid.kdBP, ret.lateralTuning.pid.kdV = [[0.], [0.]]

    if candidate in [CAR.PRIUS, CAR.PRIUS_2019]:
      stop_and_go = True
      ret.safetyParam = 66  # see conversion factor for STEER_TORQUE_EPS in dbc file
      ret.wheelbase = 2.70
      ret.steerRatio = 15.74   # unknown end-to-end spec
      tire_stiffness_factor = 0.6371   # hand-tune
      ret.mass = 3045. * CV.LB_TO_KG + STD_CARGO_KG

      ret.lateralTuning.init('indi')
      ret.lateralTuning.indi.innerLoopGain = 4.0
      ret.lateralTuning.indi.outerLoopGainBP = [0.]
      ret.lateralTuning.indi.outerLoopGainV = [3.]
      ret.lateralTuning.indi.timeConstant = 1.0
      ret.lateralTuning.indi.actuatorEffectiveness = 1.0
      ret.steerActuatorDelay = 0.5

    elif candidate == CAR.PRIUS_TSS2:
      #ret.longitudinalTuning.kpV = [0.4, 0.36, 0.325]  # braking tune from rav4h
      #ret.longitudinalTuning.kiV = [0.195, 0.10]
      ret.longitudinalTuning.kpV = [1.8, 0.75, 0.31]
      ret.longitudinalTuning.kiV = [0.18, 0.13]
      stop_and_go = True
      ret.safetyParam = 55
      ret.wheelbase = 2.70002
      ret.steerRatio = 13.4   # True steerRation from older prius
      tire_stiffness_factor = 0.6371   # hand-tune
      ret.mass = 3115. * CV.LB_TO_KG + STD_CARGO_KG
      ret.steerActuatorDelay = 0.5
      if prius_pid:
        ret.lateralTuning.init('pid')
        ret.lateralTuning.pid.kiBP, ret.lateralTuning.pid.kpBP, ret.lateralTuning.pid.kfBP = [[0.], [0.], [0.]]
        ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.21], [0.008]]
        ret.lateralTuning.pid.kdBP = [0.]
        ret.lateralTuning.pid.kdV = [1.0]
        ret.lateralTuning.pid.kfV = [0.00009531750004645412]
      else:
        ret.lateralTuning.init('indi')
        ret.lateralTuning.indi.innerLoopGain = 4.0
        ret.lateralTuning.indi.outerLoopGainBP = [0.]
        ret.lateralTuning.indi.outerLoopGainV = [3.0]
        ret.lateralTuning.indi.timeConstant = 0.1
        ret.lateralTuning.indi.actuatorEffectiveness = 1.0

    elif candidate in [CAR.RAV4H]:
      stop_and_go = True if (candidate in CAR.RAV4H) else False
      ret.safetyParam = 73
      ret.wheelbase = 2.65
      ret.steerRatio = 16.88   # 14.5 is spec end-to-end
      tire_stiffness_factor = 0.5533
      ret.mass = 3650. * CV.LB_TO_KG + STD_CARGO_KG  # mean between normal and hybrid
      ret.lateralTuning.init('lqr')

      ret.lateralTuning.lqr.scale = 1500.0
      ret.lateralTuning.lqr.ki = 0.06

      ret.lateralTuning.lqr.a = [0., 1., -0.22619643, 1.21822268]
      ret.lateralTuning.lqr.b = [-1.92006585e-04, 3.95603032e-05]
      ret.lateralTuning.lqr.c = [1., 0.]
      ret.lateralTuning.lqr.k = [-110.73572306, 451.22718255]
      ret.lateralTuning.lqr.l = [0.3233671, 0.3185757]
      ret.lateralTuning.lqr.dcGain = 0.002237852961363602

    elif candidate in [CAR.RAV4]:
      stop_and_go = True if (candidate in CAR.RAV4H) else False
      ret.safetyParam = 73
      ret.wheelbase = 2.65
      ret.steerRatio = 16.88   # 14.5 is spec end-to-end
      tire_stiffness_factor = 0.5533
      ret.mass = 3650. * CV.LB_TO_KG + STD_CARGO_KG  # mean between normal and hybrid
      ret.lateralTuning.init('lqr')

      ret.lateralTuning.lqr.scale = 1500.0
      ret.lateralTuning.lqr.ki = 0.06
      ret.longitudinalTuning.kpV = [0.8, 1.0, 0.325]  # braking tune
      ret.longitudinalTuning.kiV = [0.35, 0.1]
      ret.lateralTuning.lqr.a = [0., 1., -0.22619643, 1.21822268]
      ret.lateralTuning.lqr.b = [-1.92006585e-04, 3.95603032e-05]
      ret.lateralTuning.lqr.c = [1., 0.]
      ret.lateralTuning.lqr.k = [-110.73572306, 451.22718255]
      ret.lateralTuning.lqr.l = [0.3233671, 0.3185757]
      ret.lateralTuning.lqr.dcGain = 0.002237852961363602

    elif candidate in [CAR.COROLLA, CAR.COROLLA_2015]:
      stop_and_go = False
      ret.safetyParam = 88
      ret.wheelbase = 2.70
      ret.steerRatio = 18.27
      tire_stiffness_factor = 0.444  # not optimized yet
      ret.mass = 2860. * CV.LB_TO_KG + STD_CARGO_KG  # mean between normal and hybrid
      ret.lateralTuning.init('lqr')

      ret.lateralTuning.lqr.scale = 1500.0
      ret.lateralTuning.lqr.ki = 0.06

      ret.lateralTuning.lqr.a = [0., 1., -0.22619643, 1.21822268]
      ret.lateralTuning.lqr.b = [-1.92006585e-04, 3.95603032e-05]
      ret.lateralTuning.lqr.c = [1., 0.]
      ret.lateralTuning.lqr.k = [-110.73572306, 451.22718255]
      ret.lateralTuning.lqr.l = [0.3233671, 0.3185757]
      ret.lateralTuning.lqr.dcGain = 0.002237852961363602

    elif candidate == CAR.LEXUS_RX:
      stop_and_go = True
      ret.safetyParam = 73
      ret.wheelbase = 2.79
      ret.steerRatio = 14.8
      tire_stiffness_factor = 0.5533
      ret.mass = 4387. * CV.LB_TO_KG + STD_CARGO_KG
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.6], [0.05]]
      ret.lateralTuning.pid.kfV = [0.00006]

    elif candidate == CAR.LEXUS_RXH:
      stop_and_go = True
      ret.safetyParam = 73
      ret.wheelbase = 2.79
      ret.steerRatio = 16.  # 14.8 is spec end-to-end
      tire_stiffness_factor = 0.444  # not optimized yet
      ret.mass = 4481. * CV.LB_TO_KG + STD_CARGO_KG  # mean between min and max
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.6], [0.1]]
      ret.lateralTuning.pid.kfV = [0.00006]   # full torque for 10 deg at 80mph means 0.00007818594

    elif candidate == CAR.LEXUS_RX_TSS2:
      stop_and_go = True
      ret.safetyParam = 55
      ret.wheelbase = 2.79
      ret.steerRatio = 14.8
      tire_stiffness_factor = 0.5533  # not optimized yet
      ret.mass = 4387. * CV.LB_TO_KG + STD_CARGO_KG
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.6], [0.1]]
      ret.lateralTuning.pid.kfV = [0.00007818594]

    elif candidate == CAR.LEXUS_RXH_TSS2:
      stop_and_go = True
      ret.safetyParam = 55
      ret.wheelbase = 2.79
      ret.steerRatio = 16.0  # 14.8 is spec end-to-end
      tire_stiffness_factor = 0.444  # not optimized yet
      ret.mass = 4481.0 * CV.LB_TO_KG + STD_CARGO_KG  # mean between min and max
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.6], [0.15]]
      ret.lateralTuning.pid.kfV = [0.00007818594]

    elif candidate in [CAR.CHR, CAR.CHRH]:
      stop_and_go = True
      ret.safetyParam = 73
      ret.wheelbase = 2.63906
      ret.steerRatio = 13.6
      tire_stiffness_factor = 0.7933
      ret.mass = 3300. * CV.LB_TO_KG + STD_CARGO_KG
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.723], [0.0428]]
      ret.lateralTuning.pid.kfV = [0.00006]

    elif candidate in [CAR.CAMRY, CAR.CAMRYH]:
      stop_and_go = True
      ret.safetyParam = 73
      ret.wheelbase = 2.82448
      ret.steerRatio = 13.7
      tire_stiffness_factor = 0.7933
      ret.mass = 3400. * CV.LB_TO_KG + STD_CARGO_KG  # mean between normal and hybrid
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.6], [0.1]]
      ret.lateralTuning.pid.kfV = [0.00006]

    elif candidate in [CAR.HIGHLANDER_TSS2, CAR.HIGHLANDERH_TSS2]:
      stop_and_go = True
      ret.safetyParam = 55
      ret.wheelbase = 2.84988  # 112.2 in = 2.84988 m
      ret.steerRatio = 16.0
      tire_stiffness_factor = 0.8
      ret.mass = 4700. * CV.LB_TO_KG + STD_CARGO_KG  # 4260 + 4-5 people
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.18], [0.015]]  # community tuning
      ret.lateralTuning.pid.kfV = [0.00012]  # community tuning

    elif candidate in [CAR.HIGHLANDER, CAR.HIGHLANDERH]:
      stop_and_go = True
      ret.safetyParam = 73
      ret.wheelbase = 2.78
      ret.steerRatio = 16.0
      tire_stiffness_factor = 0.8
      ret.mass = 4607. * CV.LB_TO_KG + STD_CARGO_KG  # mean between normal and hybrid limited
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.18], [0.015]]  # community tuning
      ret.lateralTuning.pid.kfV = [0.00012]  # community tuning

    elif candidate in [CAR.AVALON, CAR.AVALON_2021]:
      stop_and_go = False
      ret.safetyParam = 73
      ret.wheelbase = 2.82
      ret.steerRatio = 14.8  # Found at https://pressroom.toyota.com/releases/2016+avalon+product+specs.download
      tire_stiffness_factor = 0.7983
      ret.mass = 3505. * CV.LB_TO_KG + STD_CARGO_KG  # mean between normal and hybrid
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.17], [0.03]]
      ret.lateralTuning.pid.kfV = [0.00006]

    elif candidate == CAR.RAV4_TSS2:
      stop_and_go = True
      ret.safetyParam = 56 # from cabana https://discord.com/channels/469524606043160576/574796986822295569/781874934661775400
      ret.wheelbase = 2.68986
      ret.steerRatio = 14.3
      tire_stiffness_factor = 0.7933
      ret.mass = 3370. * CV.LB_TO_KG + STD_CARGO_KG
      ret.longitudinalTuning.kpV = [2.1, 1.2, 0.34]
      ret.longitudinalTuning.kiV = [0.54, 0.34]  # minor double braking still remains
      if spairrowtuning:
        ret.steerActuatorDelay = 0.12
        ret.steerRatio = 15.33
        ret.steerLimitTimer = 5.0
        tire_stiffness_factor = 0.996  # not optimized yet
        ret.lateralTuning.init('indi')
        ret.lateralTuning.indi.innerLoopGain = 21
        ret.lateralTuning.indi.outerLoopGainBP = [20, 21, 25, 26]
        ret.lateralTuning.indi.outerLoopGainV = [14, 20.99, 20.99, 23] # 14 low speed turns, 20.99 for lane centering, 23 high speed stability
        ret.lateralTuning.indi.timeConstant = 6.0
        ret.lateralTuning.indi.actuatorEffectiveness = 21
      else:
        ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.15], [0.05]]
        ret.lateralTuning.pid.kfV = [0.00004]
        for fw in car_fw:
          if fw.ecu == "eps" and fw.fwVersion == b"8965B42170\x00\x00\x00\x00\x00\x00":
            ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.6], [0.1]]
            ret.lateralTuning.pid.kfV = [0.00007818594]
            break

    elif candidate == CAR.RAV4H_TSS2:
      stop_and_go = True
      ret.safetyParam = 55
      ret.wheelbase = 2.68986
      ret.steerRatio = 13.99
      tire_stiffness_factor = 0.7933
      ret.longitudinalTuning.kpV = [0.2, 0.25, 0.325]
      ret.longitudinalTuning.kiV = [0.10, 0.10]
      if spairrowtuning:
        ret.steerActuatorDelay = 0.12
        ret.steerRatio = 15.33
        ret.steerLimitTimer = 5.0
        tire_stiffness_factor = 0.996  # not optimized yet
        ret.lateralTuning.init('indi')
        ret.lateralTuning.indi.innerLoopGain = 21.0
        ret.lateralTuning.indi.outerLoopGainBP = [20, 21, 25, 26]
        ret.lateralTuning.indi.outerLoopGainV = [11.0, 16.5, 17.0, 21.0]
        ret.lateralTuning.indi.timeConstant = 8.0
        ret.lateralTuning.indi.actuatorEffectiveness = 21.0
      else:
        ret.lateralTuning.init('pid')
        ret.lateralTuning.pid.kiBP, ret.lateralTuning.pid.kpBP, ret.lateralTuning.pid.kfBP = [[0.,14], [0.,14], [0.]]
        ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.24, 0.18], [0.04, 0.03]]
        ret.mass = 3800. * CV.LB_TO_KG + STD_CARGO_KG
        ret.lateralTuning.pid.kfV = [0.00004]
        for fw in car_fw:
          if fw.ecu == "eps" and fw.fwVersion == b"8965B42170\x00\x00\x00\x00\x00\x00":
            ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.25, 0.55], [0.05, 0.1]]
            ret.lateralTuning.pid.kfV = [0.00007818594]
            break


    elif candidate == CAR.COROLLA_TSS2:
      stop_and_go = True
      ret.safetyParam = 55
      ret.wheelbase = 2.63906
      ret.steerRatio = 13.9
      tire_stiffness_factor = 0.444  # not optimized yet
      ret.mass = 3060. * CV.LB_TO_KG + STD_CARGO_KG
      ret.longitudinalTuning.kpV = [0.4, 0.36, 0.325]  # braking tune from rav4h
      ret.longitudinalTuning.kiV = [0.195, 0.10]
      if spairrowtuning:
        ret.safetyParam = 53
        ret.steerActuatorDelay = 0.60
        ret.steerRatio = 15.33
        ret.steerLimitTimer = 5.0
        tire_stiffness_factor = 0.996  # not optimized yet
        ret.lateralTuning.init('indi')
        ret.lateralTuning.indi.innerLoopGain = 15.0
        ret.lateralTuning.indi.outerLoopGainBP = [20, 21, 25 ,26]
        ret.lateralTuning.indi.outerLoopGainV = [4.0, 8.5, 9.0, 14.99]
        ret.lateralTuning.indi.timeConstant = 5.5
        ret.lateralTuning.indi.actuatorEffectiveness = 15.0
      else:
        ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.5], [0.1]]
        ret.lateralTuning.pid.kfV = [0.00007818594]
        if corolla_tss2_d_tuning:
          ret.steerActuatorDelay = 0.40
          ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.6], [0.1]]
          ret.lateralTuning.pid.kdV = [9.0]
          ret.lateralTuning.pid.kfV = [0.00007818594]

    elif candidate == CAR.COROLLAH_TSS2:
      ret.longitudinalTuning.kpV = [0.25, 0.3, 0.325]  # braking tune from rav4h
      ret.longitudinalTuning.kiV = [0.068, 0.10]
      stop_and_go = True
      ret.safetyParam = 55
      ret.wheelbase = 2.63906
      ret.steerRatio = 13.9
      tire_stiffness_factor = 0.444  # not optimized yet
      ret.mass = 3060. * CV.LB_TO_KG + STD_CARGO_KG
      if spairrowtuning:
        ret.safetyParam = 53
        ret.steerActuatorDelay = 0.60
        ret.steerRatio = 15.33
        ret.steerLimitTimer = 5.0
        tire_stiffness_factor = 0.996  # not optimized yet
        ret.lateralTuning.init('indi')
        ret.lateralTuning.indi.innerLoopGain = 15.0
        ret.lateralTuning.indi.outerLoopGainBP = [20, 21, 25 ,26]
        ret.lateralTuning.indi.outerLoopGainV = [4.0, 8.5, 9.0, 14.99]
        ret.lateralTuning.indi.timeConstant = 5.5
        ret.lateralTuning.indi.actuatorEffectiveness = 15.0
      else:
        ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.5], [0.1]]
        ret.lateralTuning.pid.kfV = [0.00007818594]
        if corolla_tss2_d_tuning:
          ret.steerActuatorDelay = 0.40
          ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.6], [0.1]]
          ret.lateralTuning.pid.kdV = [9.0]

    elif candidate in [CAR.LEXUS_ES_TSS2, CAR.LEXUS_ESH_TSS2]:
      stop_and_go = True
      ret.safetyParam = 55
      ret.wheelbase = 2.8702
      ret.steerRatio = 16.0  # not optimized
      tire_stiffness_factor = 0.444  # not optimized yet
      ret.mass = 3704. * CV.LB_TO_KG + STD_CARGO_KG
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.6], [0.1]]
      ret.lateralTuning.pid.kfV = [0.00007818594]

    elif candidate == CAR.SIENNA:
      stop_and_go = True
      ret.safetyParam = 73
      ret.wheelbase = 3.03
      ret.steerRatio = 15.5
      tire_stiffness_factor = 0.444
      ret.mass = 4590. * CV.LB_TO_KG + STD_CARGO_KG
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.19], [0.02]]
      ret.lateralTuning.pid.kfV = [0.00007818594]

    elif candidate in [CAR.LEXUS_IS, CAR.LEXUS_ISH, CAR.LEXUS_RX]:
      stop_and_go = False
      ret.safetyParam = 77
      ret.wheelbase = 2.79908
      ret.steerRatio = 13.3
      tire_stiffness_factor = 0.444
      ret.mass = 3736.8 * CV.LB_TO_KG + STD_CARGO_KG
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.3], [0.05]]
      ret.lateralTuning.pid.kfV = [0.00006]

    elif candidate == CAR.LEXUS_CTH:
      stop_and_go = True
      ret.safetyParam = 100
      ret.wheelbase = 2.60
      ret.steerRatio = 18.6
      tire_stiffness_factor = 0.517
      ret.mass = 3108 * CV.LB_TO_KG + STD_CARGO_KG  # mean between min and max
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.291], [0.035]]
      ret.lateralTuning.pid.kfV = [0.00004]

    elif candidate == CAR.LEXUS_NXH:
      stop_and_go = True
      ret.safetyParam = 73
      ret.wheelbase = 2.66
      ret.steerRatio = 14.7
      tire_stiffness_factor = 0.444  # not optimized yet
      ret.mass = 4070 * CV.LB_TO_KG + STD_CARGO_KG
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.6], [0.1]]
      ret.lateralTuning.pid.kfV = [0.00006]

    elif candidate == CAR.LEXUS_NXH:
      stop_and_go = True
      ret.safetyParam = 73
      ret.wheelbase = 2.66
      ret.steerRatio = 14.7
      tire_stiffness_factor = 0.444 # not optimized yet
      ret.mass = 4070 * CV.LB_TO_KG + STD_CARGO_KG
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.6], [0.1]]
      ret.lateralTuning.pid.kfV = [0.00006]

    elif candidate == CAR.LEXUS_UXH_TSS2:
      stop_and_go = True
      ret.safetyParam = 55
      ret.wheelbase = 2.640
      ret.steerRatio = 16.0  # not optimized
      tire_stiffness_factor = 0.444  # not optimized yet
      ret.mass = 3500. * CV.LB_TO_KG + STD_CARGO_KG
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.6], [0.1]]
      ret.lateralTuning.pid.kfV = [0.00007]

    ret.steerRateCost = 0.5
    ret.centerToFront = ret.wheelbase * 0.44

    # TODO: get actual value, for now starting with reasonable value for
    # civic and scaling by mass and wheelbase
    ret.rotationalInertia = scale_rot_inertia(ret.mass, ret.wheelbase)

    # TODO: start from empirically derived lateral slip stiffness for the civic and scale by
    # mass and CG position, so all cars will have approximately similar dyn behaviors
    ret.tireStiffnessFront, ret.tireStiffnessRear = scale_tire_stiffness(ret.mass, ret.wheelbase, ret.centerToFront,
                                                                         tire_stiffness_factor=tire_stiffness_factor)
    if candidate == CAR.COROLLA_2015:
      ret.enableCamera = True
    else:
      ret.enableCamera = is_ecu_disconnected(fingerprint[0], FINGERPRINTS, ECU_FINGERPRINT, candidate, Ecu.fwdCamera) or has_relay
    # Detect smartDSU, which intercepts ACC_CMD from the DSU allowing openpilot to send it
    smartDsu = 0x2FF in fingerprint[0]
    # In TSS2 cars the camera does long control
    ret.enableDsu = is_ecu_disconnected(fingerprint[0], FINGERPRINTS, ECU_FINGERPRINT, candidate, Ecu.dsu) and candidate not in TSS2_CAR
    ret.enableGasInterceptor = 0x201 in fingerprint[0]
    # if the smartDSU is detected, openpilot can send ACC_CMD (and the smartDSU will block it from the DSU) or not (the DSU is "connected")
    ret.openpilotLongitudinalControl = ret.enableCamera and (smartDsu or ret.enableDsu or candidate in TSS2_CAR)
    cloudlog.warning("ECU Camera Simulated: %r", ret.enableCamera)
    cloudlog.warning("ECU DSU Simulated: %r", ret.enableDsu)
    cloudlog.warning("ECU Gas Interceptor: %r", ret.enableGasInterceptor)

    # min speed to enable ACC. if car can do stop and go, then set enabling speed
    # to a negative value, so it won't matter.
    ret.minEnableSpeed = -1. if (stop_and_go or ret.enableGasInterceptor) else 19. * CV.MPH_TO_MS

    # removing the DSU disables AEB and it's considered a community maintained feature
    # intercepting the DSU is a community feature since it requires unofficial hardware
    ret.communityFeature = ret.enableGasInterceptor or ret.enableDsu or smartDsu

    ret.longitudinalTuning.deadzoneBP = [0., 9.]
    ret.longitudinalTuning.deadzoneV = [0., .15]

    ret.longitudinalTuning.kpBP = [0., 5., 55.]
    ret.longitudinalTuning.kiBP = [0., 55.]

    return ret

  # returns a car.CarState
  def update(self, c, can_strings):
    self.sm.update(0)
    # ******************* do can recv *******************
    self.cp_cam.update_strings(can_strings)
    if self.frame < 1000:
      self.cp.update_strings(can_strings)
      ret = self.CS.update(self.cp, self.cp_cam, self.frame)
    else:
      self.cp.update_strings(can_strings)
      ret = self.CS.update(self.cp, self.cp_cam, self.frame)

    # create message
    ret_arne182 = arne182.CarStateArne182.new_message()
    ret.canValid = self.cp.can_valid
    if self.CP.carFingerprint != CAR.COROLLA_2015:
      ret.canValid = ret.canValid and self.cp_cam.can_valid
    ret.steeringRateLimited = self.CC.steer_rate_limited if self.CC is not None else False

    # gear except P, R
    extra_gears = [GearShifter.neutral, GearShifter.eco, GearShifter.manumatic, GearShifter.drive, GearShifter.sport, GearShifter.low, GearShifter.brake, GearShifter.unknown]

    longControlDisabled = False
    # cruise state
    if not self.CS.out.cruiseState.enabled:
      self.waiting = False
      ret.cruiseState.enabled = self.CS.pcm_acc_active
    else:
      if self.keep_openpilot_engaged:
        ret.cruiseState.enabled = bool(self.CS.main_on)
      if not self.CS.pcm_acc_active:
        longControlDisabled = True
        ret.brakePressed = True
        self.waiting = False
        self.disengage_due_to_slow_speed = False
    if ret.vEgo < 1 or not self.keep_openpilot_engaged:
      ret.cruiseState.enabled = self.CS.pcm_acc_active
      if self.CS.out.cruiseState.enabled and not self.CS.pcm_acc_active:
        self.disengage_due_to_slow_speed = True
    if self.disengage_due_to_slow_speed and ret.vEgo > 1 and ret.gearShifter != GearShifter.reverse:
      self.disengage_due_to_slow_speed = False
      ret.cruiseState.enabled = bool(self.CS.main_on)


     #do we need the two commented out?
    #ret.canValid = self.cp.can_valid and self.cp_cam.can_valid
    #ret.steeringRateLimited = self.CC.steer_rate_limited if self.CC is not None else False

    # events
    events, events_arne182 = self.create_common_events(ret, extra_gears)

    if longControlDisabled:
      events_arne182.add(EventNameArne182.longControlDisabled)

    ret.buttonEvents = []
    if self.cp_cam.can_invalid_cnt >= 200 and self.CP.enableCamera and self.CP.carFingerprint != CAR.COROLLA_2015:
      events.add(EventName.invalidGiraffeToyota)

    if not self.waiting and ret.vEgo < 0.3 and not ret.gasPressed and self.CP.carFingerprint == CAR.RAV4H:
      self.waiting = True
    if self.waiting:
      if ret.gasPressed:
        self.waiting = False
      else:
        events_arne182.add(EventNameArne182.waitingMode)

    if ret.rightBlinker and self.CS.rightblindspot and ret.vEgo > self.alca_min_speed and self.sm['pathPlan'].laneChangeState  == LaneChangeState.preLaneChange:
      events_arne182.add(EventNameArne182.rightALCbsm)
    if ret.leftBlinker and self.CS.leftblindspot and ret.vEgo > self.alca_min_speed and self.sm['pathPlan'].laneChangeState  == LaneChangeState.preLaneChange:
      events_arne182.add(EventNameArne182.leftALCbsm)

    if self.CS.low_speed_lockout and self.CP.openpilotLongitudinalControl:
      events.add(EventName.lowSpeedLockout)
    if ret.vEgo < self.CP.minEnableSpeed and self.CP.openpilotLongitudinalControl:
      events.add(EventName.belowEngageSpeed)
      if c.actuators.gas > 0.1:
        # some margin on the actuator to not false trigger cancellation while stopping
        events.add(EventName.speedTooLow)
      if ret.vEgo < 0.001:
        # while in standstill, send a user alert
        events.add(EventName.manualRestart)
    ret.events = events.to_msg()
    ret_arne182.events = events_arne182.to_msg()

    self.CS.out = ret.as_reader()
    return self.CS.out, ret_arne182.as_reader()

  # pass in a car.CarControl
  # to be called @ 100hz
  def apply(self, c):

    can_sends = self.CC.update(c.enabled, self.CS, self.frame,
                               c.actuators, c.cruiseControl.cancel,
                               c.hudControl.visualAlert, c.hudControl.leftLaneVisible,
                               c.hudControl.rightLaneVisible, c.hudControl.leadVisible,
                               c.hudControl.leftLaneDepart, c.hudControl.rightLaneDepart)

    self.frame += 1
    return can_sends
