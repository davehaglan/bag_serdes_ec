# -*- coding: utf-8 -*-

"""This module defines classes needed to build the Hybrid-QDR FFE/DFE summer."""

from typing import TYPE_CHECKING, Dict, Any, Set

from itertools import chain

from bag.layout.template import TemplateBase
from bag.layout.routing.base import TrackManager

from ..laygo.misc import LaygoDummy
from ..laygo.divider import SinClkDivider
from .amp import IntegAmp

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class TapXSummerCell(TemplateBase):
    """A summer cell containing a single DFE/FFE tap with the corresponding latch.

    Parameters
    ----------
    temp_db : TemplateDB
            the template database.
    lib_name : str
        the layout library name.
    params : Dict[str, Any]
        the parameter values.
    used_names : Set[str]
        a set of already used cell names.
    **kwargs
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._lat_row_layout_info = None
        self._lat_track_info = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def lat_row_layout_info(self):
        # type: () -> Dict[str, Any]
        return self._lat_row_layout_info

    @property
    def lat_track_info(self):
        # type: () -> Dict[str, Any]
        return self._lat_track_info

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            flip_sign=False,
            end_mode=12,
            show_pins=True,
            options=None,
        )

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w_sum='NMOS/PMOS width dictionary for summer.',
            w_lat='NMOS/PMOS width dictionary for latch.',
            th_sum='NMOS/PMOS threshold flavor dictionary.',
            th_lat='NMOS/PMOS threshold dictoary for latch.',
            seg_sum='number of segments dictionary for summer tap.',
            seg_lat='number of segments dictionary for latch.',
            fg_duml='Number of left edge dummy fingers.',
            fg_dumr='Number of right edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            flip_sign='True to flip summer output sign.',
            end_mode='The AnalogBase end_mode flag.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        # get parameters
        fg_duml = self.params['fg_duml']
        fg_dumr = self.params['fg_dumr']
        flip_sign = self.params['flip_sign']
        end_mode = self.params['end_mode']
        show_pins = self.params['show_pins']

        # get layout parameters
        top_layer = IntegAmp.get_mos_conn_layer(self.grid.tech_info) + 2
        sum_params = dict(
            w_dict=self.params['w_sum'],
            th_dict=self.params['th_sum'],
            seg_dict=self.params['seg_sum'],
            top_layer=top_layer,
            flip_sign=flip_sign,
            show_pins=False,
            end_mode=end_mode,
        )
        lat_params = dict(
            w_dict=self.params['w_lat'],
            th_dict=self.params['th_lat'],
            seg_dict=self.params['seg_lat'],
            top_layer=top_layer,
            flip_sign=False,
            show_pins=False,
            end_mode=end_mode & 0b1100,
        )
        for key in ('lch', 'ptap_w', 'ntap_w', 'fg_duml', 'fg_dumr', 'tr_widths',
                    'tr_spaces', 'options'):
            sum_params[key] = lat_params[key] = self.params[key]

        # get masters
        l_master = self.new_template(params=lat_params, temp_cls=IntegAmp)
        s_master = self.new_template(params=sum_params, temp_cls=IntegAmp)
        if l_master.fg_tot < s_master.fg_tot:
            # update latch master
            fg_inc = s_master.fg_tot - l_master.fg_tot
            fg_inc2 = fg_inc // 2
            fg_duml2 = fg_duml + fg_inc2
            fg_dumr2 = fg_dumr + fg_inc - fg_inc2
            l_master = l_master.new_template_with(fg_duml=fg_duml2, fg_dumr=fg_dumr2)
        elif s_master.fg_tot < l_master.fg_tot:
            fg_inc = l_master.fg_tot - s_master.fg_tot
            fg_inc2 = fg_inc // 2
            fg_duml2 = fg_duml + fg_inc2
            fg_dumr2 = fg_dumr + fg_inc - fg_inc2
            s_master = s_master.new_template_with(fg_duml=fg_duml2, fg_dumr=fg_dumr2)

        # place instances
        s_inst = self.add_instance(s_master, 'XSUM', loc=(0, 0), unit_mode=True)
        y0 = s_inst.array_box.top_unit + l_master.array_box.top_unit
        d_inst = self.add_instance(l_master, 'XLAT', loc=(0, y0), orient='MX', unit_mode=True)

        # set size
        self.array_box = s_inst.array_box.merge(d_inst.array_box)
        self.set_size_from_bound_box(top_layer, s_inst.bound_box.merge(d_inst.bound_box))

        # export pins in-place
        exp_list = [(s_inst, 'clkp', 'clkn', True), (s_inst, 'clkn', 'clkp', True),
                    (s_inst, 'casc', 'casc', False),
                    (s_inst, 'inp', 'outp_l', True), (s_inst, 'inn', 'outn_l', True),
                    (s_inst, 'biasp', 'biasn_s', False),
                    (s_inst, 'en<3>', 'en<2>', True), (s_inst, 'en<2>', 'en<1>', False),
                    (s_inst, 'setp', 'setp', False), (s_inst, 'setn', 'setn', False),
                    (s_inst, 'pulse', 'pulse', False),
                    (s_inst, 'outp', 'outp_s', False), (s_inst, 'outn', 'outn_s', False),
                    (s_inst, 'VDD', 'VDD', True), (s_inst, 'VSS', 'VSS', True),
                    (d_inst, 'clkp', 'clkp', True), (d_inst, 'clkn', 'clkn', True),
                    (d_inst, 'inp', 'inp', False), (d_inst, 'inn', 'inn', False),
                    (d_inst, 'biasp', 'biasp_l', False),
                    (d_inst, 'en<3>', 'en<3>', True), (d_inst, 'en<2>', 'en<2>', True),
                    (d_inst, 'setp', 'setp', False), (d_inst, 'setn', 'setn', False),
                    (d_inst, 'pulse', 'pulse', False),
                    (d_inst, 'outp', 'outp_l', True), (d_inst, 'outn', 'outn_l', True),
                    (d_inst, 'VDD', 'VDD', True), (d_inst, 'VSS', 'VSS', True),
                    ]

        for inst, port_name, name, vconn in exp_list:
            if inst.has_port(port_name):
                port = inst.get_port(port_name)
                label = name + ':' if vconn else name
                self.reexport(port, net_name=name, label=label, show=show_pins)

        # set schematic parameters
        self._sch_params = dict(
            sum_params=s_master.sch_params,
            lat_params=l_master.sch_params,
        )
        self._lat_row_layout_info = l_master.row_layout_info
        self._lat_track_info = l_master.track_info


class TapXSummerLast(TemplateBase):
    """A summer cell containing DFE tap2 gm cell with divider/pulse gen/dummies.

    Parameters
    ----------
    temp_db : TemplateDB
            the template database.
    lib_name : str
        the layout library name.
    params : Dict[str, Any]
        the parameter values.
    used_names : Set[str]
        a set of already used cell names.
    **kwargs
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._fg_core = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_core(self):
        # type: () -> int
        return self._fg_core

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            div_pos_edge=True,
            flip_sign=False,
            fg_min=0,
            end_mode=12,
            show_pins=True,
            options=None,
        )

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='Laygo configuration dictionary for the divider.',
            row_layout_info='The AnalogBase layout information dictionary for divider.',
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w_sum='NMOS/PMOS width dictionary for summer.',
            th_sum='NMOS/PMOS threshold flavor dictionary.',
            seg_sum='number of segments dictionary for summer tap.',
            seg_div='number of segments dictionary for clock divider.',
            seg_pul='number of segments dictionary for pulse generation.',
            fg_duml='Number of left edge dummy fingers.',
            fg_dumr='Number of right edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            lat_tr_info='latch output track information dictionary.',
            div_pos_edge='True if the divider triggers off positive edge of the clock.',
            flip_sign='True to flip summer output sign.',
            fg_min='Minimum number of core fingers.',
            end_mode='The AnalogBase end_mode flag.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        # get parameters
        row_layout_info = self.params['row_layout_info']
        seg_div = self.params['seg_div']
        seg_pul = self.params['seg_pul']
        fg_duml = self.params['fg_duml']
        fg_dumr = self.params['fg_dumr']
        lat_tr_info = self.params['lat_tr_info']
        div_pos_edge = self.params['div_pos_edge']
        flip_sign = self.params['flip_sign']
        fg_min = self.params['fg_min']
        end_mode = self.params['end_mode']
        show_pins = self.params['show_pins']

        no_dig = (seg_div is None and seg_pul is None)

        # get layout parameters
        top_layer = IntegAmp.get_mos_conn_layer(self.grid.tech_info) + 2
        sum_params = dict(
            w_dict=self.params['w_sum'],
            th_dict=self.params['th_sum'],
            seg_dict=self.params['seg_sum'],
            top_layer=top_layer,
            flip_sign=flip_sign,
            show_pins=False,
            end_mode=end_mode,
        )
        for key in ('lch', 'ptap_w', 'ntap_w', 'fg_duml', 'fg_dumr',
                    'tr_widths', 'tr_spaces', 'options'):
            sum_params[key] = self.params[key]

        s_master = self.new_template(params=sum_params, temp_cls=IntegAmp)
        fg_core = s_master.layout_info.fg_core
        fg_min = max(fg_min, fg_core)

        dig_params = dict(
            config=self.params['config'],
            row_layout_info=row_layout_info,
            tr_widths=self.params['tr_widths'],
            tr_spaces=self.params['tr_spaces'],
            end_mode=end_mode & 0b1100,
            show_pins=False,
        )
        if no_dig:
            # no digital block, draw LaygoDummy
            if fg_core < fg_min:
                fg_inc = fg_min - fg_core
                fg_inc2 = fg_inc // 2
                fg_duml2 = fg_duml + fg_inc2
                fg_dumr2 = fg_dumr + fg_inc - fg_inc2
                s_master = s_master.new_template_with(fg_duml=fg_duml2, fg_dumr=fg_dumr2)

            tr_info = dict(
                VDD=lat_tr_info['VDD'],
                VSS=lat_tr_info['VSS'],
            )
            dig_params['num_col'] = s_master.fg_tot
            dig_params['tr_info'] = tr_info
            d_master = self.new_template(params=dig_params, temp_cls=LaygoDummy)
            div_sch_params = pul_sch_params = None
        else:
            # draw divider
            tr_info = dict(
                VDD=lat_tr_info['VDD'],
                VSS=lat_tr_info['VSS'],
                q=lat_tr_info['outp'],
                qb=lat_tr_info['outn'],
                en=lat_tr_info['nen3'],
                clk=lat_tr_info['clkp'] if div_pos_edge else lat_tr_info['clkn'],
            )
            dig_params['seg_dict'] = seg_div
            dig_params['tr_info'] = tr_info
            dig_params['fg_min'] = fg_min
            d_master = self.new_template(params=dig_params, temp_cls=SinClkDivider)
            div_sch_params = d_master.sch_params
            pul_sch_params = None
            fg_min = max(fg_min, d_master.laygo_info.core_col)

            if fg_core < fg_min:
                fg_inc = fg_min - fg_core
                fg_inc2 = fg_inc // 2
                fg_duml2 = fg_duml + fg_inc2
                fg_dumr2 = fg_dumr + fg_inc - fg_inc2
                s_master = s_master.new_template_with(fg_duml=fg_duml2, fg_dumr=fg_dumr2)

        # TODO: add pulse generator logic here

        # place instances
        s_inst = self.add_instance(s_master, 'XSUM', loc=(0, 0), unit_mode=True)
        y0 = s_inst.array_box.top_unit + d_master.array_box.top_unit
        d_inst = self.add_instance(d_master, 'XDIG', loc=(0, y0), orient='MX', unit_mode=True)

        # set size
        self.array_box = s_inst.array_box.merge(d_inst.array_box)
        self.set_size_from_bound_box(top_layer, s_inst.bound_box.merge(d_inst.bound_box))

        # get pins
        vconn_clkp = vconn_clkn = False
        # export digital pins
        self.reexport(d_inst.get_port('VDD'), label='VDD:', show=show_pins)
        self.reexport(d_inst.get_port('VSS'), label='VSS:', show=show_pins)
        if seg_div is not None:
            # perform connections for divider
            if div_pos_edge:
                clk_name = 'clkp'
                vconn_clkp = True
            else:
                clk_name = 'clkn'
                vconn_clkn = True

            # re-export divider pins
            self.reexport(d_inst.get_port('clk'), net_name=clk_name, label=clk_name + ':',
                          show=show_pins)
            self.reexport(d_inst.get_port('q'), net_name='div', show=show_pins)
            self.reexport(d_inst.get_port('qb'), net_name='divb', show=show_pins)
            self.reexport(d_inst.get_port('en'), net_name='en_div', show=show_pins)
            self.reexport(d_inst.get_port('scan_s'), net_name='scan_div', show=show_pins)
        if seg_pul is not None:
            # TODO: perform connections for pulse generation
            pass

        # export pins in-place
        exp_list = [(s_inst, 'clkp', 'clkn', vconn_clkn), (s_inst, 'clkn', 'clkp', vconn_clkp),
                    (s_inst, 'inp', 'inp', False), (s_inst, 'inn', 'inn', False),
                    (s_inst, 'biasp', 'biasn', False),
                    (s_inst, 'en<3>', 'en<2>', True), (s_inst, 'en<2>', 'en<1>', False),
                    (s_inst, 'setp', 'setp', False), (s_inst, 'setn', 'setn', False),
                    (s_inst, 'pulse', 'pulse_in', False),
                    (s_inst, 'outp', 'outp', False), (s_inst, 'outn', 'outn', False),
                    (s_inst, 'VDD', 'VDD', True), (s_inst, 'VSS', 'VSS', True),
                    ]

        for inst, port_name, name, vconn in exp_list:
            if inst.has_port(port_name):
                port = inst.get_port(port_name)
                label = name + ':' if vconn else name
                self.reexport(port, net_name=name, label=label, show=show_pins)

        # set schematic parameters
        self._sch_params = dict(
            div_pos_edge=div_pos_edge,
            sum_params=s_master.sch_params,
            div_params=div_sch_params,
            pul_params=pul_sch_params,
        )
        self._fg_core = s_master.layout_info.fg_core


class TapXSummer(TemplateBase):
    """The DFE tapx summer.

    Parameters
    ----------
    temp_db : TemplateDB
            the template database.
    lib_name : str
        the layout library name.
    params : Dict[str, Any]
        the parameter values.
    used_names : Set[str]
        a set of already used cell names.
    **kwargs
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._fg_core_last = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_core_last(self):
        return self._fg_core_last

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            div_pos_edge=True,
            fg_min_last=0,
            is_end=False,
            show_pins=True,
            options=None,
        )

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='Laygo configuration dictionary for the divider.',
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w_sum='NMOS/PMOS width dictionary for summer.',
            w_lat='NMOS/PMOS width dictionary for latch.',
            th_sum='NMOS/PMOS threshold flavor dictionary.',
            th_lat='NMOS/PMOS threshold dictoary for latch.',
            seg_sum_list='list of segment dictionaries for summer taps.',
            seg_ffe_list='list of segment dictionaries for FFE latches.',
            seg_dfe_list='list of segment dictionaries for DFE latches.',
            flip_sign_list='list of flip_sign values for summer taps.',
            seg_div='number of segments dictionary for clock divider.',
            seg_pul='number of segments dictionary for pulse generation.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            div_pos_edge='True if the divider triggers off positive edge of the clock.',
            fg_min_last='Minimum number of core fingers for last cell.',
            is_end='True if this is the end row.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        # get parameters
        config = self.params['config']
        lch = self.params['lch']
        ptap_w = self.params['ptap_w']
        ntap_w = self.params['ntap_w']
        w_sum = self.params['w_sum']
        w_lat = self.params['w_lat']
        th_sum = self.params['th_sum']
        th_lat = self.params['th_lat']
        seg_sum_list = self.params['seg_sum_list']
        seg_ffe_list = self.params['seg_ffe_list']
        seg_dfe_list = self.params['seg_dfe_list']
        flip_sign_list = self.params['flip_sign_list']
        seg_div = self.params['seg_div']
        seg_pul = self.params['seg_pul']
        fg_dum = self.params['fg_dum']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        div_pos_edge = self.params['div_pos_edge']
        fg_min_last = self.params['fg_min_last']
        is_end = self.params['is_end']
        show_pins = self.params['show_pins']
        options = self.params['options']

        num_sum = len(seg_sum_list)
        num_ffe = len(seg_ffe_list)
        num_dfe = len(seg_dfe_list) + 1
        if num_sum != num_ffe + num_dfe or num_sum != len(flip_sign_list):
            raise ValueError('segment dictionary list length mismatch.')
        if num_ffe < 1:
            raise ValueError('Must have at least one FFE (last FFE is main tap).')
        end_mode = 1 if is_end else 0

        # create layout masters
        ffe_masters = []
        ffe_sch_params = []
        for idx in range(num_ffe):
            seg_ffe = seg_ffe_list[idx]
            seg_sum = seg_sum_list[idx]
            flip_sign = flip_sign_list[idx]
            cur_end = end_mode | 0b0100 if idx == num_ffe - 1 else end_mode
            cur_params = dict(lch=lch, ptap_w=ptap_w, ntap_w=ntap_w, w_sum=w_sum, w_lat=w_lat,
                              th_sum=th_sum, th_lat=th_lat, seg_sum=seg_sum, seg_lat=seg_ffe,
                              fg_duml=fg_dum, fg_dumr=fg_dum, tr_widths=tr_widths,
                              tr_spaces=tr_spaces, flip_sign=flip_sign, end_mode=cur_end,
                              show_pins=False, options=options,
                              )
            cur_master = self.new_template(params=cur_params, temp_cls=TapXSummerCell)
            ffe_masters.append(cur_master)
            ffe_sch_params.append(cur_master.sch_params)

        dfe_masters = []
        dfe_sch_params = []
        for idx in range(num_dfe - 1):
            seg_dfe = seg_dfe_list[idx]
            seg_sum = seg_sum_list[idx + 1 + num_ffe]
            flip_sign = flip_sign_list[idx + 1 + num_ffe]
            cur_params = dict(lch=lch, ptap_w=ptap_w, ntap_w=ntap_w, w_sum=w_sum, w_lat=w_lat,
                              th_sum=th_sum, th_lat=th_lat, seg_sum=seg_sum, seg_lat=seg_dfe,
                              fg_duml=fg_dum, fg_dumr=fg_dum, tr_widths=tr_widths,
                              tr_spaces=tr_spaces, flip_sign=flip_sign, end_mode=end_mode,
                              show_pins=False, options=options,
                              )
            cur_master = self.new_template(params=cur_params, temp_cls=TapXSummerCell)
            dfe_masters.append(self.new_template(params=cur_params, temp_cls=TapXSummerCell))
            dfe_sch_params.append(cur_master.sch_params)

        main = ffe_masters[0]
        last_params = dict(config=config, row_layout_info=main.lat_row_layout_info,
                           lch=lch, ptap_w=ptap_w, ntap_w=ntap_w, w_sum=w_sum, th_sum=th_sum,
                           seg_sum=seg_sum_list[num_ffe], seg_div=seg_div, seg_pul=seg_pul,
                           fg_duml=fg_dum, fg_dumr=fg_dum, tr_widths=tr_widths, tr_spaces=tr_spaces,
                           lat_tr_info=main.lat_track_info, div_pos_edge=div_pos_edge,
                           flip_sign=flip_sign_list[num_ffe], fg_min=fg_min_last,
                           end_mode=end_mode | 0b1000, show_pins=False, options=options
                           )
        last_master = self.new_template(params=last_params, temp_cls=TapXSummerLast)
        last_sch_params = last_master.sch_params

        # place instances
        x0 = 0
        top_layer = main.top_layer
        ffe_insts, dfe_insts = [], []
        vdd_list, vss_list = [], []
        for fidx in range(num_ffe - 1, -1, -1):
            master = ffe_masters[fidx]
            inst = self.add_instance(master, 'XFFE%d' % fidx, loc=(x0, 0), unit_mode=True)
            x0 = inst.array_box.right_unit
            ffe_insts.insert(0, inst)
            vdd_list.extend(inst.port_pins_iter('VDD'))
            vss_list.extend(inst.port_pins_iter('VSS'))
        for didx in range(num_dfe + 1, 2, -1):
            master = dfe_masters[didx - 3]
            inst = self.add_instance(master, 'XDFE%d' % didx, loc=(x0, 0), unit_mode=True)
            x0 = inst.array_box.right_unit
            dfe_insts.insert(0, inst)
            vdd_list.extend(inst.port_pins_iter('VDD'))
            vss_list.extend(inst.port_pins_iter('VSS'))
        instl = self.add_instance(last_master, 'XDFE2', loc=(x0, 0), unit_mode=True)
        vdd_list.extend(instl.port_pins_iter('VDD'))
        vss_list.extend(instl.port_pins_iter('VSS'))
        # set size
        self.array_box = instl.array_box.merge(ffe_insts[-1].array_box)
        self.set_size_from_bound_box(top_layer, instl.bound_box.merge(ffe_insts[-1].bound_box))

        # add pins
        # connect supplies
        vdd_list = self.connect_wires(vdd_list)
        vss_list = self.connect_wires(vss_list)
        self.add_pin('VDD', vdd_list, label='VDD:', show=show_pins)
        self.add_pin('VSS', vss_list, label='VSS:', show=show_pins)

        # export/collect FFE pins
        biasm_list, biasa_list, clkp_list, clkn_list = [], [], [], []
        outs_warrs = [[], []]
        en_warrs = [[], [], [], []]
        for fidx, inst in enumerate(ffe_insts):
            if inst.has_port('casc'):
                self.reexport(inst.get_port('casc'), net_name='casc<%d>' % fidx, show=show_pins)
            biasm_list.append(inst.get_pin('biasn_s'))
            self.reexport(inst.get_port('inp'), net_name='inp_a<%d>' % fidx, show=show_pins)
            self.reexport(inst.get_port('inn'), net_name='inn_a<%d>' % fidx, show=show_pins)
            biasa_list.append(inst.get_pin('biasp_l'))
            clkp_list.extend(inst.port_pins_iter('clkp'))
            clkn_list.extend(inst.port_pins_iter('clkn'))
            en_warrs[3].extend(inst.port_pins_iter('en<3>'))
            en_warrs[2].extend(inst.port_pins_iter('en<2>'))
            if inst.has_port('en<1>'):
                en_warrs[1].extend(inst.port_pins_iter('en<1>'))
            # TODO: handle setp/setn/pulse pins
            outs_warrs[0].append(inst.get_pin('outp_s'))
            outs_warrs[1].append(inst.get_pin('outn_s'))
            self.reexport(inst.get_port('outp_l'), net_name='outp_a<%d>' % fidx,
                          label='outp_a<%d>:' % fidx, show=show_pins)
            self.reexport(inst.get_port('outn_l'), net_name='outn_a<%d>' % fidx,
                          label='outn_a<%d>:' % fidx, show=show_pins)

        # export/collect DFE pins
        biasd_list = []
        for idx, inst in enumerate(dfe_insts):
            didx = idx + 3
            self.reexport(inst.get_port('biasn_s'), net_name='biasn_s<%d>' % didx,
                          show=show_pins)
            self.reexport(inst.get_port('inp'), net_name='inp_d<%d>' % didx, show=show_pins)
            self.reexport(inst.get_port('inn'), net_name='inn_d<%d>' % didx, show=show_pins)
            biasd_list.append(inst.get_pin('biasp_l'))
            clkp_list.extend(inst.port_pins_iter('clkp'))
            clkn_list.extend(inst.port_pins_iter('clkn'))
            en_warrs[3].extend(inst.port_pins_iter('en<3>'))
            en_warrs[2].extend(inst.port_pins_iter('en<2>'))
            if inst.has_port('en<1>'):
                en_warrs[1].extend(inst.port_pins_iter('en1>'))
            # TODO: handle setp/setn/pulse pins
            outs_warrs[0].append(inst.get_pin('outp_s'))
            outs_warrs[1].append(inst.get_pin('outn_s'))
            self.reexport(inst.get_port('outp_l'), net_name='outp_d<%d>' % didx,
                          label='outp_d<%d>:' % didx, show=show_pins)
            self.reexport(inst.get_port('outn_l'), net_name='outn_d<%d>' % didx,
                          label='outn_d<%d>:' % didx, show=show_pins)

        # export/collect last summer tap pins
        self.reexport(instl.get_port('inp'), net_name='inp_d<2>', show=show_pins)
        self.reexport(instl.get_port('inn'), net_name='inn_d<2>', show=show_pins)
        self.reexport(instl.get_port('biasn'), net_name='biasn_s<2>', show=show_pins)
        en_warrs[2].extend(instl.port_pins_iter('en<2>'))
        if instl.has_port('en<1>'):
            en_warrs[1].extend(instl.port_pins_iter('en<1>'))
        # TODO: handle setp/setn/pulse pins
        if instl.has_port('clkp'):
            clkp_list.extend(instl.port_pins_iter('clkp'))
            clkn_list.extend(instl.port_pins_iter('clkn'))
        if instl.has_port('div'):
            for name in ('en_div', 'scan_div', 'div', 'divb'):
                self.reexport(instl.get_port(name), show=show_pins)
        # TODO: handle pulse generation pins
        outs_warrs[0].append(instl.get_pin('outp'))
        outs_warrs[1].append(instl.get_pin('outn'))

        # connect wires and add pins
        biasm = self.connect_wires(biasm_list)
        biasa = self.connect_wires(biasa_list)
        biasd = self.connect_wires(biasd_list)
        clkp = self.connect_wires(clkp_list)
        clkn = self.connect_wires(clkn_list)
        outsp = self.connect_wires(outs_warrs[0])
        outsn = self.connect_wires(outs_warrs[1])
        self.add_pin('biasn_m', biasm, show=show_pins)
        self.add_pin('biasp_a', biasa, show=show_pins)
        self.add_pin('biasp_d', biasd, show=show_pins)
        self.add_pin('clkp', clkp, label='clkp:', show=show_pins)
        self.add_pin('clkn', clkn, label='clkn:', show=show_pins)
        self.add_pin('outp_s', outsp, show=show_pins)
        self.add_pin('outn_s', outsn, show=show_pins)

        for idx, en_warr in enumerate(en_warrs):
            if en_warr:
                en_warr = self.connect_wires(en_warr)
                name = 'en<%d>' % idx
                self.add_pin(name, en_warr, label=name + ':', show=show_pins)

        self._sch_params = dict(
            ffe_params_list=ffe_sch_params,
            dfe_params_list=dfe_sch_params,
            last_params=last_sch_params,
        )
        self._fg_core_last = last_master.fg_core


class TapXColumn(TemplateBase):
    """The column of DFE tap1 summers.

    Parameters
    ----------
    temp_db : TemplateDB
            the template database.
    lib_name : str
        the layout library name.
    params : Dict[str, Any]
        the parameter values.
    used_names : Set[str]
        a set of already used cell names.
    **kwargs
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            show_pins=True,
            options=None,
        )

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='Laygo configuration dictionary for the divider.',
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w_sum='NMOS/PMOS width dictionary for summer.',
            w_lat='NMOS/PMOS width dictionary for latch.',
            th_sum='NMOS/PMOS threshold flavor dictionary.',
            th_lat='NMOS/PMOS threshold dictoary for latch.',
            seg_sum_list='list of segment dictionaries for summer taps.',
            seg_ffe_list='list of segment dictionaries for FFE latches.',
            seg_dfe_list='list of segment dictionaries for DFE latches.',
            flip_sign_list='list of flip_sign values for summer taps.',
            seg_div='number of segments dictionary for clock divider.',
            seg_pul='number of segments dictionary for pulse generation.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        # get parameters
        show_pins = self.params['show_pins']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']

        res = self.grid.resolution

        # make masters
        div_params = self.params.copy()
        div_params['seg_pul'] = None
        div_params['div_pos_edge'] = True
        div_params['is_end'] = False
        div_params['show_pins'] = False

        divn_master = self.new_template(params=div_params, temp_cls=TapXSummer)
        fg_min_last = divn_master.fg_core_last

        end_params = self.params.copy()
        end_params['seg_div'] = None
        end_params['fg_min_last'] = fg_min_last
        end_params['is_end'] = True
        end_params['show_pins'] = False

        endb_master = self.new_template(params=end_params, temp_cls=TapXSummer)
        if endb_master.fg_core_last > fg_min_last:
            fg_min_last = endb_master.fg_core_last
            divn_master = divn_master.new_template_with(fg_min_last=fg_min_last)

        divp_master = divn_master.new_template_with(div_pos_edge=False)
        endt_master = endb_master.new_template_with(seg_pul=None)

        # place instances
        vm_layer = endt_master.top_layer
        inst3 = self.add_instance(endb_master, 'X3', loc=(0, 0), unit_mode=True)
        ycur = inst3.array_box.top_unit + divn_master.array_box.top_unit
        inst0 = self.add_instance(divp_master, 'X0', loc=(0, ycur), orient='MX', unit_mode=True)
        ycur = inst0.array_box.top_unit
        inst2 = self.add_instance(divn_master, 'X2', loc=(0, ycur), unit_mode=True)
        ycur = inst2.array_box.top_unit + endt_master.array_box.top_unit
        inst1 = self.add_instance(endt_master, 'X1', loc=(0, ycur), orient='MX', unit_mode=True)
        inst_list = [inst0, inst1, inst2, inst3]

        # set size
        self.set_size_from_bound_box(vm_layer, inst1.bound_box.merge(inst3.bound_box))
        self.array_box = self.bound_box

        # re-export supply pins
        vdd_list = list(chain(*(inst.port_pins_iter('VDD') for inst in inst_list)))
        vss_list = list(chain(*(inst.port_pins_iter('VSS') for inst in inst_list)))
        self.add_pin('VDD', vdd_list, label='VDD:', show=show_pins)
        self.add_pin('VSS', vss_list, label='VSS:', show=show_pins)

        # draw wires
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        # re-export ports, and gather wires
        en_warrs = [[], [], [], []]
        biasm_warrs = [0, 0, 0, 0]
        clk_warrs = [[], []]
        biasa_warrs = [[], []]
        biasd_warrs = [[], []]
        for idx, inst in enumerate(inst_list):
            pidx = (idx + 1) % 4
            nidx = (idx - 1) % 4
            biasm_warrs[nidx] = inst.get_pin('biasn_m')
            for off in range(4):
                en_pin = 'en<%d>' % off
                en_idx = (off + idx + 1) % 4
                if inst.has_port(en_pin):
                    en_warrs[en_idx].extend(inst.port_pins_iter(en_pin))
            if inst.has_port('div'):
                if idx == 0:
                    idxp, idxn = 3, 1
                else:
                    idxp, idxn = 2, 0
                en_warrs[idxp].extend(inst.port_pins_iter('div'))
                en_warrs[idxn].extend(inst.port_pins_iter('divb'))

            self.reexport(inst.get_port('outp_s'), net_name='outp<%d>' % nidx, show=show_pins)
            self.reexport(inst.get_port('outn_s'), net_name='outn<%d>' % nidx, show=show_pins)
            self.reexport(inst.get_port('inp_d<2>'), net_name='inp_d<%d>' % pidx, show=show_pins)
            self.reexport(inst.get_port('inn_d<2>'), net_name='inn_d<%d>' % pidx, show=show_pins)
            if idx % 2 == 1:
                biasa_warrs[0].extend(inst.port_pins_iter('biasp_a'))
                biasd_warrs[0].extend(inst.port_pins_iter('biasp_d'))
                clk_warrs[0].extend(inst.port_pins_iter('clkp'))
                clk_warrs[1].extend(inst.port_pins_iter('clkn'))
            else:
                biasa_warrs[1].extend(inst.port_pins_iter('biasp_a'))
                biasd_warrs[1].extend(inst.port_pins_iter('biasp_d'))
                clk_warrs[1].extend(inst.port_pins_iter('clkp'))
                clk_warrs[0].extend(inst.port_pins_iter('clkn'))