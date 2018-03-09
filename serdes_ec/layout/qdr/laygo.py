# -*- coding: utf-8 -*-

"""This module contains LaygoBase templates used in QDR receiver."""

from typing import TYPE_CHECKING, Dict, Any, Set

from abs_templates_ec.laygo.core import LaygoBase

from bag.layout.routing import TrackManager, TrackID

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class SinClkDivider(LaygoBase):
    """A Sinusoidal clock divider using LaygoBase.

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
    **kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        LaygoBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='laygo configuration dictionary.',
            row_layout_info='The AnalogBase layout information dictionary.',
            seg_dict='Number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            show_pins='True to show pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(show_pins=True)

    def draw_layout(self):
        row_layout_info = self.params['row_layout_info']
        seg_dict = self.params['seg_dict'].copy()
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        show_pins = self.params['show_pins']

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        blk_sp = seg_dict['blk_sp']
        seg_inv = self._get_gate_inv_info(seg_dict)
        seg_int = self._get_integ_amp_info(seg_dict)
        seg_sr = self._get_sr_latch_info(seg_dict)
        num_col = seg_inv + seg_int + seg_sr + 2 * blk_sp

        self.set_rows_direct(row_layout_info, num_col=num_col)

        vss_warr, vdd_warr1, vdd_warr2 = self._draw_substrate(num_col)
        col_inv = 0
        col_int = col_inv + seg_inv + blk_sp
        col_sr = col_int + seg_int + blk_sp
        inv_ports = self._draw_gate_inv(col_inv, seg_inv, seg_dict, tr_manager)
        int_ports = self._draw_integ_amp(col_int, seg_int, seg_dict, tr_manager)
        sr_ports, xm_locs = self._draw_sr_latch(col_sr, seg_sr, seg_dict, tr_manager)

        # connect inverters to integ amp
        en_warrs = self.connect_to_track_wires(inv_ports['en'], int_ports['en'])
        clk_warrs = self.connect_to_track_wires(inv_ports['clk'], int_ports['clk'])
        mp = inv_ports['mp']
        mn = inv_ports['mn']
        tr_upper = mp.upper
        tr_w = mp.track_id.width
        mp_tid = mp.track_id.base_index
        mn_tid = mn.track_id.base_index
        mp, mn = self.connect_differential_tracks(int_ports['mp'], int_ports['mn'],
                                                  mp.layer_id, mp_tid, mn_tid,
                                                  width=tr_w, track_upper=tr_upper)

        # connect integ amp to sr latch
        sb = self.connect_wires([int_ports['sb'], sr_ports['sb']])
        rb = self.connect_wires([int_ports['rb'], sr_ports['rb']])

        # connect sr latch to inverters
        xm_layer = self.conn_layer + 3
        xm_w_q = tr_manager.get_width(xm_layer, 'out')
        q_warrs = [inv_ports['q'], sr_ports['q']]
        qb_warrs = [inv_ports['qb'], sr_ports['qb']]
        q, qb = self.connect_differential_tracks(q_warrs, qb_warrs, xm_layer, xm_locs[1],
                                                 xm_locs[0], width=xm_w_q)

        # connect supply wires
        vss_warrs = [vss_warr, int_ports['VSS']]
        vss_warrs.extend(sr_ports['VSS'])
        vss_warrs.extend(inv_ports['VSS'])
        vdd_warrs = [vdd_warr1]
        vdd_warrs.extend(int_ports['VDD'])
        vdd_warrs.extend(sr_ports['VDD'])
        self.connect_wires(vss_warrs)
        self.connect_wires(vdd_warrs)
        self.connect_wires([vdd_warr2, inv_ports['VDD']])

        self.fill_space()

        self.add_pin('en', en_warrs, show=show_pins)
        self.add_pin('clk', clk_warrs, show=show_pins)
        self.add_pin('mp', mp, show=show_pins)
        self.add_pin('mn', mn, show=show_pins)
        self.add_pin('sb', sb, show=show_pins)
        self.add_pin('rb', rb, show=show_pins)
        self.add_pin('q', q, show=show_pins)
        self.add_pin('qb', qb, show=show_pins)
        self.add_pin('scan_r', sr_ports['scan_r'], show=show_pins)
        self.add_pin('scan_s', sr_ports['scan_s'], show=show_pins)

    def _draw_substrate(self, num_col):
        nsub = self.add_laygo_mos(0, 0, num_col)
        psub = self.add_laygo_mos(self.num_rows - 1, 0, num_col)
        return nsub['VSS_s'], psub['VDD_s'], psub['VDD_d']

    @classmethod
    def _get_gate_inv_info(cls, seg_dict):
        seg_pen = seg_dict['inv_pen']
        seg_inv = seg_dict['inv_inv']

        if seg_inv % 2 != 0:
            raise ValueError('This generator only works for even inv_inv.')
        if seg_pen % 4 != 2:
            raise ValueError('This generator only works for seg_pen = 2 mod 4.')

        return 2 * seg_inv + (seg_pen + 2)

    @classmethod
    def _get_integ_amp_info(cls, seg_dict):
        seg_rst = seg_dict['int_rst']
        seg_pen = seg_dict['int_pen']
        seg_in = seg_dict['int_in']

        if seg_rst % 2 != 0 or seg_pen % 2 != 0 or seg_in % 2 != 0:
            raise ValueError('This generator only works for even sr_inv/sr_drv/sr_sp.')

        return 2 * max(seg_in, seg_rst + seg_pen)

    @classmethod
    def _get_sr_latch_info(cls, seg_dict):
        seg_inv = seg_dict['sr_inv']
        seg_drv = seg_dict['sr_drv']
        seg_set = seg_dict['sr_set']
        seg_sp = seg_dict['sr_sp']
        seg_nand = seg_dict['sr_nand']

        if seg_inv % 2 != 0 or seg_drv % 2 != 0 or seg_sp % 2 != 0:
            raise ValueError('This generator only works for even sr_inv/sr_drv/sr_sp.')
        if seg_sp < 2:
            raise ValueError('sr_sp must be >= 2.')

        seg_nand_set = max(seg_nand * 2, seg_set)
        return (seg_inv + seg_drv + seg_sp + seg_nand_set) * 2

    def _draw_gate_inv(self, start, seg_tot, seg_dict, tr_manager):
        blk_sp = seg_dict['blk_sp']
        seg_pen = seg_dict['inv_pen']
        seg_inv = seg_dict['inv_inv']

        xleft = self.laygo_info.col_to_coord(start, 's', unit_mode=True)
        xright = self.laygo_info.col_to_coord(start + seg_tot, 's', unit_mode=True)

        col_inv = start + (seg_pen + 2) // 2
        ridx = 3
        ninvl = self.add_laygo_mos(ridx, col_inv, seg_inv)
        pinvl = self.add_laygo_mos(ridx + 1, col_inv, seg_inv)
        col_inv += seg_inv
        ninvr = self.add_laygo_mos(ridx, col_inv, seg_inv)
        pinvr = self.add_laygo_mos(ridx + 1, col_inv, seg_inv)
        pgate = self.add_laygo_mos(ridx + 2, start, seg_tot, gate_loc='s')

        # get track indices
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        hm_w_in = tr_manager.get_width(hm_layer, 'in')
        hm_w_out = tr_manager.get_width(hm_layer, 'out')
        vm_w_in = tr_manager.get_width(vm_layer, 'in')
        vm_w_out = tr_manager.get_width(vm_layer, 'out')
        in_start, in_stop = self.get_track_interval(3, 'g')
        nin_locs = tr_manager.spread_wires(hm_layer, ['in', 'in'], in_stop - in_start,
                                           'in', alignment=1, start_idx=in_start)
        gb_idx0 = self.get_track_index(3, 'gb', 0)
        gb_idx1 = self.get_track_index(4, 'gb', 0)
        ntr = gb_idx1 - gb_idx0 + 1
        out_locs = tr_manager.spread_wires(hm_layer, ['', 'out', '', 'out', ''], ntr,
                                           'out', alignment=0, start_idx=gb_idx0)
        pin_idx0 = self.get_track_index(4, 'g', -1)
        clk_idx = self.get_track_index(5, 'g', -1)
        en_idx = clk_idx + 1
        tleft = self.grid.coord_to_nearest_track(vm_layer, xleft, unit_mode=True, half_track=True,
                                                 mode=1)
        tright = self.grid.coord_to_nearest_track(vm_layer, xright, unit_mode=True, half_track=True,
                                                  mode=-1)
        ntr = tright - tleft + 1
        vin_locs = tr_manager.align_wires(vm_layer, ['in', 'in'], ntr, alignment=0, start_idx=tleft)
        xleft = self.laygo_info.col_to_coord(col_inv + seg_inv, 's', unit_mode=True)
        xright = self.laygo_info.col_to_coord(start + seg_tot + blk_sp, 's', unit_mode=True)
        tleft = self.grid.coord_to_nearest_track(vm_layer, xleft, unit_mode=True, half_track=True,
                                                 mode=1)
        tright = self.grid.coord_to_nearest_track(vm_layer, xright, unit_mode=True, half_track=True,
                                                  mode=-1)
        ntr = tright - tleft + 1
        vout_locs = tr_manager.align_wires(vm_layer, ['out', 'out'], ntr, alignment=0,
                                           start_idx=tleft)

        # connect outputs
        outp = [ninvr['d'], pinvr['d']]
        outn = [ninvl['d'], pinvl['d']]
        outp, outn = self.connect_differential_tracks(outp, outn, hm_layer, out_locs[3],
                                                      out_locs[1], width=hm_w_out)
        outp, outn = self.connect_differential_tracks(outp, outn, vm_layer, vout_locs[1],
                                                      vout_locs[0], width=vm_w_out)

        # connect inputs
        ninp, ninn = self.connect_differential_tracks(ninvl['g'], ninvr['g'], hm_layer, nin_locs[1],
                                                      nin_locs[0], width=hm_w_in)
        pinp, pinn = self.connect_differential_tracks(pinvl['g'], pinvr['g'], hm_layer, pin_idx0,
                                                      pin_idx0 + 1, width=hm_w_in)
        inp, inn = self.connect_differential_tracks([ninp, pinp], [ninn, pinn], vm_layer,
                                                    vin_locs[0], vin_locs[1], width=vm_w_in)

        # connect enables and clocks
        num_en = (seg_pen + 2) // 4
        pgate_warrs = pgate['g'].to_warr_list()
        en_warrs = pgate_warrs[:num_en] + pgate_warrs[-num_en:]
        en = self.connect_to_tracks(en_warrs, TrackID(hm_layer, en_idx))
        clk_warrs = pgate_warrs[num_en:-num_en]
        clk = self.connect_to_tracks(clk_warrs, TrackID(hm_layer, clk_idx))

        return {'VDD': pgate['d'], 'VSS': [ninvl['s'], ninvr['s']],
                'mp': outp, 'mn': outn,
                'qb': inp, 'q': inn,
                'en': en, 'clk': clk}

    def _draw_integ_amp(self, start, seg_tot, seg_dict, tr_manager):
        seg_rst = seg_dict['int_rst']
        seg_pen = seg_dict['int_pen']
        seg_in = seg_dict['int_in']

        xleft = self.laygo_info.col_to_coord(start, 'd', unit_mode=True)
        xright = self.laygo_info.col_to_coord(start + seg_tot - 1, 's', unit_mode=True)

        # place instances
        seg_single = seg_tot // 2
        ridx = 1
        nclk = self.add_laygo_mos(ridx, start, seg_tot)
        nen = self.add_laygo_mos(ridx + 1, start, seg_tot, gate_loc='s')
        col_l = start + seg_single - seg_in
        inl = self.add_laygo_mos(ridx + 2, col_l, seg_in)
        inr = self.add_laygo_mos(ridx + 2, col_l + seg_in, seg_in)
        ridx = 4
        col = start + seg_single - seg_rst - seg_pen
        penl = self.add_laygo_mos(ridx, col, seg_pen)
        col += seg_pen
        rstl = self.add_laygo_mos(ridx, col, seg_rst)
        col += seg_rst
        rstr = self.add_laygo_mos(ridx, col, seg_rst)
        col += seg_rst
        penr = self.add_laygo_mos(ridx, col, seg_pen)

        # get track locations
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        hm_w_tail = tr_manager.get_width(hm_layer, 'tail')
        hm_w_in = tr_manager.get_width(hm_layer, 'in')
        hm_w_out = tr_manager.get_width(hm_layer, 'out')
        vm_w_out = tr_manager.get_width(vm_layer, 'out')
        vm_w_clk = tr_manager.get_width(vm_layer, 'clk')
        tail_off = tr_manager.place_wires(hm_layer, ['tail'])[1][0]
        in_start, in_stop = self.get_track_interval(3, 'g')
        in_locs = tr_manager.spread_wires(hm_layer, ['in', 'in'], in_stop - in_start,
                                          'in', alignment=1, start_idx=in_start)
        gb_idx0 = self.get_track_index(3, 'gb', 0)
        gb_idx1 = self.get_track_index(4, 'gb', 0)
        ntr = gb_idx1 - gb_idx0 + 1
        out_locs = tr_manager.spread_wires(hm_layer, ['', 'out', '', 'out', ''], ntr,
                                           'out', alignment=0, start_idx=gb_idx0)
        pg_start = self.get_track_interval(4, 'g')[0]
        pg_locs = tr_manager.place_wires(hm_layer, ['', '', 'in', 'in'], start_idx=pg_start)[1]
        tleft = self.grid.coord_to_nearest_track(vm_layer, xleft, unit_mode=True, half_track=True,
                                                 mode=1)
        tright = self.grid.coord_to_nearest_track(vm_layer, xright, unit_mode=True, half_track=True,
                                                  mode=-1)
        ntr = tright - tleft + 1
        vm_locs = tr_manager.spread_wires(vm_layer, ['', 'out', 'clk', 'out', ''], ntr,
                                          'out', alignment=0, start_idx=tleft)

        # connect intermediate wires
        tidx = self.get_track_index(1, 'gb', 0)
        self.connect_to_tracks([nclk['d'], nen['d']],
                               TrackID(hm_layer, tidx + tail_off, width=hm_w_tail))
        tidx = self.get_track_index(2, 'gb', 0)
        self.connect_to_tracks([nen['s'], inl['s'], inr['s']],
                               TrackID(hm_layer, tidx + tail_off, width=hm_w_tail))

        # connect gate wires
        inp, inn = self.connect_differential_tracks(inl['g'], inr['g'], hm_layer, in_locs[1],
                                                    in_locs[0], width=hm_w_in)

        # connect enables
        en = self.connect_to_tracks(nen['g'], self.make_track_id(2, 'g', -1))
        enl = self.connect_to_tracks(penl['g'], TrackID(hm_layer, pg_locs[1]), min_len_mode=0)
        enr = self.connect_to_tracks(penr['g'], TrackID(hm_layer, pg_locs[1]), min_len_mode=0)
        enl = self.connect_to_tracks([en, enl], TrackID(vm_layer, vm_locs[0]))
        enr = self.connect_to_tracks([en, enr], TrackID(vm_layer, vm_locs[-1]))

        # connect clocks
        clk1 = self.connect_to_tracks(nclk['g'], self.make_track_id(1, 'g', -1))
        clk2 = self.connect_to_tracks([rstl['g'], rstr['g']], TrackID(hm_layer, pg_locs[0]))
        clk = self.connect_to_tracks([clk1, clk2], TrackID(vm_layer, vm_locs[2], width=vm_w_clk))

        # connect outputs
        outp = [inr['d'], rstr['d'], penr['d']]
        outn = [inl['d'], rstl['d'], penl['d']]
        outp, outn = self.connect_differential_tracks(outp, outn, hm_layer, out_locs[3],
                                                      out_locs[1], width=hm_w_out)
        outp, outn = self.connect_differential_tracks(outp, outn, vm_layer, vm_locs[1], vm_locs[3],
                                                      width=vm_w_out)
        outp, outn = self.connect_differential_tracks(outp, outn, hm_layer, pg_locs[3],
                                                      pg_locs[2], width=hm_w_out)

        return {'VSS': nclk['s'], 'VDD': [penl['s'], rstl['s'], rstr['s'], penr['s']],
                'mp': inp, 'mn': inn,
                'sb': outn, 'rb': outp,
                'en': [enl, enr], 'clk': clk}

    def _draw_sr_latch(self, start, seg_tot, seg_dict, tr_manager):
        seg_nand = seg_dict['sr_nand']
        seg_set = seg_dict['sr_set']
        seg_sp = seg_dict['sr_sp']
        seg_inv = seg_dict['sr_inv']
        seg_drv = seg_dict['sr_drv']
        seg_nand_set = max(seg_nand * 2, seg_set)

        # place instances
        stop = start + seg_tot
        ridx = 2
        setl = self.add_laygo_mos(ridx, start + seg_nand_set - seg_set, seg_set)
        setr = self.add_laygo_mos(ridx, stop - seg_nand_set, seg_set)
        ridx += 1
        cidx = start + seg_nand_set - seg_nand * 2
        col_spl = cidx + seg_nand * 2 + 1
        nnandl = self.add_laygo_mos(ridx, cidx, seg_nand, gate_loc='s', stack=True)
        pnandl = self.add_laygo_mos(ridx + 1, cidx, seg_nand, gate_loc='s', stack=True)
        cidx = stop - seg_nand_set
        col_spr = cidx - 1
        nnandr = self.add_laygo_mos(ridx, cidx, seg_nand, gate_loc='s', stack=True, flip=True)
        pnandr = self.add_laygo_mos(ridx + 1, cidx, seg_nand, gate_loc='s', stack=True, flip=True)
        start += seg_nand_set + seg_sp
        stop -= seg_nand_set + seg_sp

        ndrvl = self.add_laygo_mos(ridx, start, seg_drv)
        pdrvl = self.add_laygo_mos(ridx + 1, start, seg_drv)
        cidx = stop - seg_drv
        ndrvr = self.add_laygo_mos(ridx, cidx, seg_drv)
        pdrvr = self.add_laygo_mos(ridx + 1, cidx, seg_drv)
        start += seg_drv
        stop -= seg_drv

        ninvl = self.add_laygo_mos(ridx, start, seg_inv)
        pinvl = self.add_laygo_mos(ridx + 1, start, seg_inv)
        cidx = stop - seg_inv
        ninvr = self.add_laygo_mos(ridx, cidx, seg_inv)
        pinvr = self.add_laygo_mos(ridx + 1, cidx, seg_inv)

        # compute track locations
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        xm_layer = vm_layer + 1
        hm_w_in = tr_manager.get_width(hm_layer, 'in')
        hm_w_out = tr_manager.get_width(hm_layer, 'out')
        vm_w_out = tr_manager.get_width(vm_layer, 'out')
        gb_idx0 = self.get_track_index(3, 'gb', 0)
        gb_idx1 = self.get_track_index(4, 'gb', 0)
        ntr = gb_idx1 - gb_idx0 + 1
        gb_locs = tr_manager.spread_wires(hm_layer, ['', 'out', '', 'out', ''], ntr, 'out',
                                          alignment=0, start_idx=gb_idx0)
        ng_ntr, ng_locs = tr_manager.place_wires(hm_layer, ['in', 'in', '', ''])
        ng_stop = self.get_track_interval(3, 'g')[1]
        ng_locs = [idx + ng_stop - ng_ntr for idx in ng_locs]
        pg_start = self.get_track_interval(4, 'g')[0]
        pg_locs = tr_manager.place_wires(hm_layer, ['', '', 'in', 'in'], start_idx=pg_start)[1]
        ng0_tid = TrackID(hm_layer, ng_locs[3])
        ng1_tid = TrackID(hm_layer, ng_locs[2])
        pg0_tid = TrackID(hm_layer, pg_locs[0])
        pg1_tid = TrackID(hm_layer, pg_locs[1])
        setd_tid = self.make_track_id(2, 'gb', 0)
        setg_tid = self.make_track_id(2, 'g', -1)

        xl = ndrvl['d'].get_bbox_array(self.grid).xc_unit
        xr = ndrvr['d'].get_bbox_array(self.grid).xc_unit
        vm_q_idx = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True, mode=-1,
                                                    unit_mode=True)
        vm_qb_idx = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True, mode=1,
                                                     unit_mode=True)
        vm_q_tid = TrackID(vm_layer, vm_q_idx, width=vm_w_out)
        vm_qb_tid = TrackID(vm_layer, vm_qb_idx, width=vm_w_out)
        xl = self.laygo_info.col_to_coord(col_spl, 's', unit_mode=True)
        xr = self.laygo_info.col_to_coord(col_spr, 's', unit_mode=True)
        vm_s_idx = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True, mode=-1,
                                                    unit_mode=True)
        vm_r_idx = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True, mode=1,
                                                    unit_mode=True)
        vm_s_tid = TrackID(vm_layer, vm_s_idx)
        vm_r_tid = TrackID(vm_layer, vm_r_idx)
        xl = ninvl['d'].get_bbox_array(self.grid).xc_unit
        xr = ninvr['d'].get_bbox_array(self.grid).xc_unit
        vm_sb_idx = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True, mode=-1,
                                                     unit_mode=True)
        vm_rb_idx = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True, mode=1,
                                                     unit_mode=True)

        ymid = self.grid.track_to_coord(hm_layer, gb_locs[2], unit_mode=True)
        xm_mid = self.grid.coord_to_nearest_track(xm_layer, ymid, half_track=True, mode=0,
                                                  unit_mode=True)
        xm_locs = tr_manager.place_wires(xm_layer, ['out', 'out'])[1]
        mid4 = int(round((xm_locs[0] + xm_locs[1]) * 2))
        if mid4 % 4 == 0:
            mid = mid4 // 4
        elif mid4 % 4 == 2:
            mid = mid4 / 4
        elif mid4 % 4 == 1:
            mid = (mid4 - 1) // 4
        else:
            mid = (mid4 - 1) / 4
        xm_locs = [val + xm_mid - mid for val in xm_locs]

        # gather wires
        vss_list = [inst['s'] for inst in (ndrvl, ndrvr, ninvl, ninvr)]
        vdd_list = [inst['s'] for inst in (pdrvl, pdrvr, pinvl, pinvr)]
        q_list = self.connect_wires([inst['d'] for inst in (nnandl, pnandl, ndrvl, pdrvl)])
        qb_list = self.connect_wires([inst['d'] for inst in (nnandr, pnandr, ndrvr, pdrvr)])
        s_list = self.connect_wires([ninvl['d'], pinvl['d']])
        r_list = self.connect_wires([ninvr['d'], pinvr['d']])
        set_vss_list = [setl['s'], setr['s']]
        set_vss_list.extend(vss_list)
        nand_vss_list = [nnandl['s'], nnandr['s']]
        nand_vdd_list = [pnandl['s'], pnandr['s']]
        nand_vss_list.extend(vss_list)
        nand_vdd_list.extend(vdd_list)

        ports = {}
        # connect middle wires
        q_warr, qb_warr = self.connect_differential_tracks(q_list, qb_list, hm_layer, gb_locs[3],
                                                           gb_locs[1], width=hm_w_out)
        self.connect_to_tracks(nand_vss_list, TrackID(hm_layer, gb_locs[0]))
        self.connect_to_tracks(nand_vdd_list, TrackID(hm_layer, gb_locs[-1]))
        sr_tid = TrackID(hm_layer, gb_locs[2])
        s_warr = self.connect_to_tracks(s_list, sr_tid)
        r_warr = self.connect_to_tracks(r_list, sr_tid)

        # export vss/vdd
        ports['VSS'] = set_vss_list
        ports['VDD'] = vdd_list

        # connect q/qb
        for name, vtid, ninst, pinst, sinst, warr in \
                [('q', vm_q_tid, nnandl, pnandl, setl, q_warr),
                 ('qb', vm_qb_tid, nnandr, pnandr, setr, qb_warr)]:
            ng = self.connect_to_tracks(ninst['g1'], ng1_tid)
            pg = self.connect_to_tracks(pinst['g1'], pg1_tid)
            sd = self.connect_to_tracks(sinst['d'], setd_tid)
            vm_warr = self.connect_to_tracks([warr, ng, pg, sd], vtid)
            ports[name] = vm_warr

        # connect s/r
        for vtid, ninst, pinst, warr in [(vm_s_tid, ndrvl, pnandl, s_warr),
                                         (vm_r_tid, ndrvr, pnandr, r_warr)]:
            ng = self.connect_to_tracks(ninst['g'], ng0_tid)
            pg = self.connect_to_tracks(pinst['g0'], pg0_tid)
            self.connect_to_tracks([warr, pg, ng], vtid)

        # connect sb/rb
        sbb, rbb = self.connect_differential_tracks([nnandr['g0'], ninvl['g']],
                                                    [nnandl['g0'], ninvr['g']], hm_layer,
                                                    ng_locs[0], ng_locs[1], width=hm_w_in)
        sbt, rbt = self.connect_differential_tracks([pdrvr['g'], pinvl['g']],
                                                    [pdrvl['g'], pinvr['g']], hm_layer,
                                                    pg_locs[2], pg_locs[3], width=hm_w_out)
        self.connect_differential_tracks([sbb, sbt], [rbb, rbt], vm_layer,
                                         vm_sb_idx, vm_rb_idx)
        ports['sb'] = sbt
        ports['rb'] = rbt

        # connect scan_r, scan_s
        scan_r = self.connect_to_tracks(setl['g'], setg_tid, min_len_mode=0)
        scan_s = self.connect_to_tracks(setr['g'], setg_tid, min_len_mode=0)
        ports['scan_r'] = scan_r
        ports['scan_s'] = scan_s

        return ports, xm_locs
