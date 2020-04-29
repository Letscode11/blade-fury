#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import logging
import argparse

from mongoengine import Q
from pandas import DataFrame

from logger import setup_logging
from models import QuantResult as QR, StockDailyTrading as SDT
from analysis.technical_analysis_util import format_trading_data, check_duplicate_strategy, display_quant
from analysis.technical_analysis_util import calculate_ma, start_quant_analysis, collect_stock_daily_trading
from analysis.technical_analysis_util import pre_sdt_check


timeout = 60


def quant_stock(stock_number, stock_name, **kwargs):
    if not pre_sdt_check(stock_number, **kwargs):
        return

    real_time = kwargs.get('real_time', False)
    week_long = kwargs.get('week_long', False)
    strategy_direction = 'long'
    strategy_name = 'break_through_%s_%s_%s' % (strategy_direction, kwargs['short_ma'], kwargs['long_ma'])
    if week_long:
        strategy_name = 'weeklong_' + strategy_name

    sdt = SDT.objects(Q(stock_number=stock_number) &
                      Q(date__lte=kwargs['qr_date'])).order_by('-date')[:kwargs['long_ma']+10]

    if sdt is None or len(sdt) == 0:
        return
    trading_data = format_trading_data(sdt)
    df = calculate_ma(DataFrame(trading_data), short_ma, long_ma)
    # print(df)
    today = df.iloc[-1]
    yestoday = df.iloc[-2]

    if yestoday['close_price'] < yestoday['long_ma'] and today['close_price'] > today['short_ma']\
       and today['close_price'] > today['long_ma']:
        increase_rate = round((today['close_price'] - yestoday['close_price']) / yestoday['close_price'], 4) * 100
        qr = QR(
            stock_number=stock_number, stock_name=stock_name, date=today.name,
            strategy_direction=strategy_direction, strategy_name=strategy_name,
            init_price=today['close_price'], industry_involved=kwargs.get('industry_involved'),
            increase_rate=increase_rate
        )

        if real_time:
            return qr
        if not check_duplicate_strategy(qr):
            qr.save()
            return qr
    return ''


def setup_argparse():
    parser = argparse.ArgumentParser(description=u'根据突破短均线的策略选股')
    parser.add_argument(u'-s', action=u'store', dest='short_ma', required=True, help=u'短期均线数')
    parser.add_argument(u'-l', action=u'store', dest='long_ma', required=True, help=u'长期均线数')
    parser.add_argument(u'-t', action=u'store', dest='qr_date', required=False, help=u'计算均线的日期')
    parser.add_argument(u'-r', action=u'store_true', dest='real_time', required=False, help=u'是否实时计算')
    parser.add_argument(u'-w', action=u'store_true', dest='week_long', required=False, help=u'是否处于周线多头')

    args = parser.parse_args()

    if args.qr_date:
        try:
            qr_date = datetime.datetime.strptime(args.qr_date, '%Y-%m-%d').date()
        except Exception as e:
            print('Wrong date form')
            raise e
    else:
        qr_date = datetime.date.today()

    return int(args.short_ma), int(args.long_ma), qr_date, args.real_time, args.week_long


if __name__ == '__main__':
    setup_logging(__file__, logging.WARNING)
    short_ma, long_ma, qr_date, real_time, week_long = setup_argparse()
    today_trading = {}
    if real_time:
        today_trading = collect_stock_daily_trading()
    real_time_res = start_quant_analysis(short_ma=short_ma, long_ma=long_ma, qr_date=qr_date, quant_stock=quant_stock,
                                         real_time=real_time, today_trading=today_trading, week_long=week_long)
    if real_time_res and real_time:
        display_quant(real_time_res)
