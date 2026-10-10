"""Offline regression coverage for chart validation, routes and audio invariants."""
import io
import unittest
from pathlib import Path
import numpy as np
from scipy.io.wavfile import read
from fastapi.testclient import TestClient
from chart_data import CSVProvider, ChartData, summarize_chart
from spatial_audio import generate_spatial_audio, map_price_to_frequency, normalize_volume
from server import app

class ChartTests(unittest.TestCase):
    def setUp(self):
        self.csv = Path('samples/rising.csv').read_text(encoding='utf-8')
        self.chart = CSVProvider(self.csv, timeframe='1d').load()
        self.client = TestClient(app)

    def test_aliases_and_mapping(self):
        aliases=self.csv.replace('timestamp,open,high,low,close,volume','date,opening,high,low,price,vol')
        self.assertEqual(len(CSVProvider(aliases).load().candles),30)
        manual=self.csv.replace('timestamp,open,high,low,close,volume','T,O,H,L,C,V')
        mapping=dict(zip(('timestamp','open','high','low','close','volume'),('T','O','H','L','C','V')))
        self.assertEqual(CSVProvider(manual,mapping).load().candles[0].close,70000)

    def test_invalid_data(self):
        for text in ('timestamp,open,high,low,close,volume\n', self.csv.replace('70000,70100','NaN,70100',1), self.csv.replace('70000,70100','70000,69900',1),self.csv.replace(',10000\n',',-1\n',1), self.csv+self.csv.splitlines()[1]+'\n'):
            with self.subTest(text=text[:60]), self.assertRaises(ValueError): CSVProvider(text).load()

    def test_summary_uses_wicks(self):
        summary=summarize_chart(self.chart)
        self.assertEqual(summary['high'],73000)
        self.assertEqual(summary['low'],69900)
        self.assertEqual(summary['max_volume'],300000)

    def test_csv_is_internal_only(self):
        _, headers, mapping = CSVProvider(self.csv).inspect()
        self.assertEqual(mapping['close'], 'close')
        self.assertEqual(len(headers), 6)
        self.assertEqual(self.client.post('/chart-csv',files={'file':('data.csv',self.csv)}).status_code,405)
        self.assertEqual(self.client.get('/samples/rising.csv').status_code,404)
        page=self.client.get('/').text
        for removed in ('csvInput','csvPanel','analyzeCSVBtn','data-sample','CSV 다운로드'):
            self.assertNotIn(removed,page)

    def test_single_candle_and_empty(self):
        chart=CSVProvider('\n'.join(self.csv.splitlines()[:2])).load()
        response=self.client.post('/sonify-stock',json=chart.model_dump(mode='json'))
        self.assertEqual(response.status_code,200)
        _,samples=read(io.BytesIO(response.content))
        np.testing.assert_array_equal(samples[:,0],samples[:,1])
        with self.assertRaises(ValueError): generate_spatial_audio([])

    def test_segment_retains_pitch_and_pan(self):
        # Middle point of [100, 200, 300] is 400 Hz even for a one-point segment.
        _,wave=read(generate_spatial_audio([100,200,300],[1,10,100],start_index=1,end_index=1,duration_seconds=2,sample_rate=8000))
        data=wave[1000:7000,0].astype(float)
        peak=np.argmax(np.abs(np.fft.rfft(data)))*8000/len(data)
        self.assertAlmostEqual(peak,400,delta=2)
        np.testing.assert_array_equal(wave[:,0],wave[:,1])
        _,right=read(generate_spatial_audio([100,200,300],[1,10,100],start_index=2,end_index=2,duration_seconds=2,sample_rate=8000))
        self.assertEqual(np.max(np.abs(right[:,0])),0)
        self.assertGreater(np.max(np.abs(right[:,1])),100)

    def test_constant_outlier_nan_and_speed(self):
        self.assertTrue(np.all(map_price_to_frequency([10,10,10])==400))
        self.assertTrue(np.isfinite(normalize_volume([0,0,0,1e30])).all())
        spike = normalize_volume([10]*29 + [100000])
        self.assertGreater(spike[-1], spike[0])
        for prices in ([float('nan')],[float('inf')]):
            with self.assertRaises(ValueError): generate_spatial_audio(prices)
        for duration in (4,8):
            rate,audio=read(generate_spatial_audio([10,10],duration_seconds=duration,sample_rate=8000))
            signal=audio[rate:2*rate,0].astype(float)
            peak=np.argmax(np.abs(np.fft.rfft(signal)))
            self.assertAlmostEqual(peak,400,delta=2)

    def test_stock_adapter_and_image_compatibility(self):
        import cv2
        response=self.client.get('/stock-candles?demo=true&count=30')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['chart']['timeframe'],'1m')
        # A generated line graph exercises the preserved image extraction route.
        image=np.full((300,500,3),255,dtype=np.uint8)
        cv2.line(image,(20,260),(480,30),(255,0,0),4)
        _,png=cv2.imencode('.png',image)
        result=self.client.post('/analyze-graph-image',files={'image':('line.png',png.tobytes(),'image/png')},data={'chart_type':'line'})
        self.assertEqual(result.status_code,200,result.text[:200])
        self.assertGreater(len(result.json()['data']),1)

    def test_api_errors_and_public_assets(self):
        payload=self.chart.model_dump(mode='json')
        payload['start_index']=100
        self.assertEqual(self.client.post('/sonify-stock',json=payload).status_code,422)
        for path in ('/server.py','/.env','/.git/config','/README.md'):
            self.assertEqual(self.client.get(path).status_code,404,path)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/samples/rising.csv').status_code,404)
        self.assertEqual(self.client.post('/sonify-data',json={'data':[1,2,3],'max_freq':800}).status_code,200)

if __name__=='__main__': unittest.main()
