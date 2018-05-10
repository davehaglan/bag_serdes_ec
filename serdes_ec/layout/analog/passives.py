# -*- coding: utf-8 -*-


from typing import TYPE_CHECKING, Dict, Set, Any

from bag.layout.routing.base import TrackID, TrackManager
from bag.layout.util import BBox

from abs_templates_ec.resistor.core import ResArrayBase


if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class PassiveCTLECore(ResArrayBase):
    """Passive CTLE Core.

    Parameters
    ----------
    temp_db : :class:`bag.layout.template.TemplateDB`
        the template database.
    lib_name : str
        the layout library name.
    params : Dict[str, Any]
        the parameter values.
    used_names : Set[str]
        a set of already used cell names.
    **kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        ResArrayBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        return self._sch_params

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            l='unit resistor length, in meters.',
            w='unit resistor width, in meters.',
            cap_height='capacitor height, in resolution units.',
            cap_spx='Space between capacitor and left/right edge, in resolution units.',
            cap_spy='Space between capacitor and cm-port/top/bottom edge, in resolution units.',
            num_r1='number of r1 segments.',
            num_r2='number of r2 segments.',
            num_dumc='number of dummy columns.',
            num_dumr='number of dummy rows.',
            sub_type='the substrate type.',
            threshold='the substrate threshold flavor.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            res_type='the resistor type.',
            em_specs='EM specifications for the termination network.',
            show_pins='True to draw pin layous.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            res_type='standard',
            em_specs=None,
            show_pins=True,
        )

    def draw_layout(self):
        # type: () -> None

        l = self.params['l']
        w = self.params['w']
        cap_height = self.params['cap_height']
        cap_spx = self.params['cap_spx']
        cap_spy = self.params['cap_spy']
        num_r1 = self.params['num_r1']
        num_r2 = self.params['num_r2']
        num_dumc = self.params['num_dumc']
        num_dumr = self.params['num_dumr']
        sub_type = self.params['sub_type']
        threshold = self.params['threshold']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        res_type = self.params['res_type']
        em_specs = self.params['em_specs']
        show_pins = self.params['show_pins']

        res = self.grid.resolution

        if num_r1 % 2 != 0 or num_r2 % 2 != 0:
            raise ValueError('num_r1 and num_r2 must be even.')
        if num_dumc <= 0 or num_dumr <= 0:
            raise ValueError('num_dumr and num_dumc must be greater than 0.')

        # draw array
        nr1 = num_r1 // 2
        nr2 = num_r2 // 2
        hm_layer = self.bot_layer_id + 2
        top_layer = hm_layer + 1
        self.draw_array(l, w, sub_type, threshold, nx=4 + num_dumc * 2,
                        ny=2 * (max(nr1, nr2) + num_dumr), em_specs=em_specs,
                        res_type=res_type, half_blk_y=False, top_layer=top_layer)

        # connect wires
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        vm_layer = hm_layer - 1
        vm_w_io = tr_manager.get_width(vm_layer, 'ctle')
        sup_name = 'VDD' if sub_type == 'ntap' else 'VSS'
        supt, supb = self._connect_dummies(nr1, nr2, num_dumr, num_dumc)
        inp, inn, outp, outn, outcm = self._connect_snake(nr1, nr2, num_dumr, num_dumc, vm_w_io,
                                                          show_pins)

        # calculate capacitor bounding box
        bnd_box = self.bound_box
        yc = bnd_box.yc_unit
        hm_w_io = tr_manager.get_width(hm_layer, 'ctle')
        cm_tr = self.grid.coord_to_track(hm_layer, yc, unit_mode=True)
        cm_yb, cm_yt = self.grid.get_wire_bounds(hm_layer, cm_tr, width=hm_w_io, unit_mode=True)
        cap_yb = cm_yt + cap_spy
        cap_yt = min(cap_yb + cap_height, bnd_box.top_unit - cap_spy)
        cap_xl = cap_spx
        cap_xr = bnd_box.right_unit - cap_spx

        # construct port parity
        top_parity = {hm_layer: (0, 1), top_layer: (1, 0)}
        bot_parity = {hm_layer: (1, 0), top_layer: (1, 0)}
        cap_top = self.add_mom_cap(BBox(cap_xl, cap_yb, cap_xr, cap_yt, res, unit_mode=True),
                                   hm_layer, 2, port_parity=top_parity)
        cap_yt = cm_yb - cap_spy
        cap_yb = max(cap_yt - cap_height, cap_spy)
        cap_bot = self.add_mom_cap(BBox(cap_xl, cap_yb, cap_xr, cap_yt, res, unit_mode=True),
                                   hm_layer, 2, port_parity=bot_parity)

        self.connect_to_tracks(inp, cap_top[hm_layer][0][0].track_id)
        self.connect_to_tracks(outp, cap_top[hm_layer][1][0].track_id)
        self.connect_to_tracks(inn, cap_bot[hm_layer][0][0].track_id)
        self.connect_to_tracks(outn, cap_bot[hm_layer][1][0].track_id)

        self.add_pin('inp', cap_top[top_layer][0], show=show_pins)
        self.add_pin('outp', cap_top[top_layer][1], show=show_pins)
        self.add_pin('inn', cap_bot[top_layer][0], show=show_pins)
        self.add_pin('outn', cap_bot[top_layer][1], show=show_pins)
        self.add_pin(sup_name + 'B', supb, label=sup_name, show=show_pins)
        self.add_pin(sup_name + 'T', supt, label=sup_name, show=show_pins)

    def _connect_snake(self, nr1, nr2, ndumr, ndumc, io_width, show_pins):
        nrow_half = max(nr1, nr2) + ndumr
        for idx in range(nr1):
            if idx != 0:
                self._connect_mirror(nrow_half, (idx - 1, ndumc), (idx, ndumc), 1, 0)
                self._connect_mirror(nrow_half, (idx - 1, ndumc + 1), (idx, ndumc + 1), 1, 0)
            if idx == nr1 - 1:
                self._connect_mirror(nrow_half, (idx, ndumc), (idx, ndumc + 1), 1, 1)
        for idx in range(nr2):
            if idx != 0:
                self._connect_mirror(nrow_half, (idx - 1, ndumc + 2), (idx, ndumc + 2), 1, 0)
                self._connect_mirror(nrow_half, (idx - 1, ndumc + 3), (idx, ndumc + 3), 1, 0)
            if idx == nr2 - 1:
                self._connect_mirror(nrow_half, (idx, ndumc + 2), (idx, ndumc + 3), 1, 1)

        # connect outp/outn
        outpl = self.get_res_ports(nrow_half, ndumc + 1)[0]
        outpr = self.get_res_ports(nrow_half, ndumc + 2)[0]
        outp = self.connect_wires([outpl, outpr])[0]
        outnl = self.get_res_ports(nrow_half - 1, ndumc + 1)[1]
        outnr = self.get_res_ports(nrow_half - 1, ndumc + 2)[1]
        outn = self.connect_wires([outnl, outnr])[0]

        vm_layer = outp.layer_id + 1
        vm_tr = self.grid.coord_to_nearest_track(vm_layer, outp.middle, half_track=True)
        vm_tid = TrackID(vm_layer, vm_tr, width=io_width)
        outp = self.connect_to_tracks(outp, vm_tid, min_len_mode=1)
        outn = self.connect_to_tracks(outn, vm_tid, min_len_mode=-1)

        # connect inp/inn
        inp = self.get_res_ports(nrow_half, ndumc)[0]
        inn = self.get_res_ports(nrow_half - 1, ndumc)[1]
        mid = (self.get_res_ports(nrow_half, ndumc - 1)[0].middle + inp.middle) / 2
        vm_tr = self.grid.coord_to_nearest_track(vm_layer, mid, half_track=True)
        vm_tid = TrackID(vm_layer, vm_tr, width=io_width)
        inp = self.connect_to_tracks(inp, vm_tid, min_len_mode=1)
        inn = self.connect_to_tracks(inn, vm_tid, min_len_mode=-1)

        # connect outcm
        cmp = self.get_res_ports(nrow_half, ndumc + 3)[0]
        cmn = self.get_res_ports(nrow_half - 1, ndumc + 3)[1]
        vm_tr = self.grid.coord_to_nearest_track(vm_layer, cmp.middle, half_track=True)
        vm_tid = TrackID(vm_layer, vm_tr, width=io_width)
        outcm_v = self.connect_to_tracks([cmp, cmn], vm_tid)
        hm_layer = vm_layer + 1
        hm_tr = self.grid.coord_to_nearest_track(hm_layer, outcm_v.middle, half_track=True)
        outcm = self.connect_to_tracks(outcm_v, TrackID(hm_layer, hm_tr, width=io_width),
                                       track_lower=0)
        self.add_pin('outcm', outcm, show=show_pins)

        return inp, inn, outp, outn, outcm_v

    def _connect_mirror(self, offset, loc1, loc2, port1, port2):
        r1, c1 = loc1
        r2, c2 = loc2
        for sgn in (-1, 1):
            cur_r1 = offset + sgn * r1
            cur_r2 = offset + sgn * r2
            if sgn < 0:
                cur_r1 -= 1
                cur_r2 -= 1
            if sgn < 0:
                cur_port1 = 1 - port1
                cur_port2 = 1 - port2
            else:
                cur_port1 = port1
                cur_port2 = port2
            wa1 = self.get_res_ports(cur_r1, c1)[cur_port1]
            wa2 = self.get_res_ports(cur_r2, c2)[cur_port2]
            if wa1.track_id.base_index == wa2.track_id.base_index:
                self.connect_wires([wa1, wa2])
            else:
                vm_layer = wa1.layer_id + 1
                vm = self.grid.coord_to_nearest_track(vm_layer, wa1.middle, half_track=True)
                self.connect_to_tracks([wa1, wa2], TrackID(vm_layer, vm))

    def _connect_dummies(self, nr1, nr2, ndumr, ndumc):
        num_per_col = [0] * ndumc + [nr1, nr1, nr2, nr2] + [0] * ndumc
        nrow_half = max(nr1, nr2) + ndumr
        bot_warrs, top_warrs = [], []
        for col_idx, res_num in enumerate(num_per_col):
            if res_num == 0:
                cur_ndum = nrow_half * 2
                bot_idx_list = [0]
            else:
                cur_ndum = nrow_half - res_num
                bot_idx_list = [0, nrow_half + res_num]

            for bot_idx in bot_idx_list:
                top_idx = bot_idx + cur_ndum
                warr_list = []
                for ridx in range(bot_idx, top_idx):
                    bp, tp = self.get_res_ports(ridx, col_idx)
                    warr_list.append(bp)
                    warr_list.append(tp)
                vm_layer = warr_list[0].layer_id + 1
                vm = self.grid.coord_to_nearest_track(vm_layer, warr_list[0].middle,
                                                      half_track=True)
                sup_warr = self.connect_to_tracks(warr_list, TrackID(vm_layer, vm))
                if bot_idx == 0:
                    bot_warrs.append(sup_warr)
                if bot_idx != 0 or res_num == 0:
                    top_warrs.append(sup_warr)

        hm_layer = bot_warrs[0].layer_id + 1
        hm_pitch = self.grid.get_track_pitch(hm_layer, unit_mode=True)
        num_hm_tracks = self.array_box.height_unit // hm_pitch
        btr = self.connect_to_tracks(bot_warrs, TrackID(hm_layer, 0))
        ttr = self.connect_to_tracks(top_warrs, TrackID(hm_layer, num_hm_tracks - 1))

        return ttr, btr