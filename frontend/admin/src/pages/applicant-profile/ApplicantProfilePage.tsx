import { useState, useEffect, useRef, useCallback } from 'react';
import { Card, Form, Input, Select, InputNumber, Button, message, Spin, Modal } from 'antd';
import { getApplicantProfile, updateApplicantProfile } from '../../api/applicantProfile';
import type { ApplicantProfile } from '../../api/applicantProfile';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const AMAP_KEY = '85571c830d1789c299a5a3a06aadd039';
const AMAP_REST_BASE = 'https://restapi.amap.com/v3';

delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

async function amapPlaceSearch(keyword: string): Promise<Array<{ name: string; address: string; location: string }>> {
  const url = `${AMAP_REST_BASE}/place/text?key=${AMAP_KEY}&keywords=${encodeURIComponent(keyword)}&offset=10&page=1&extensions=base`;
  const res = await fetch(url);
  const data = await res.json();
  if (data.status === '1' && data.pois) {
    return data.pois.map((p: { name: string; address: string; location: string }) => ({
      name: p.name,
      address: p.address || '',
      location: p.location,
    }));
  }
  return [];
}

async function amapReverseGeocode(lng: number, lat: number): Promise<string> {
  const url = `${AMAP_REST_BASE}/geocode/regeo?key=${AMAP_KEY}&location=${lng},${lat}&radius=1000&extensions=base`;
  const res = await fetch(url);
  const data = await res.json();
  if (data.status === '1' && data.regeocode) {
    return data.regeocode.formatted_address || data.regeocode.formattedAddress || `${lat.toFixed(6)},${lng.toFixed(6)}`;
  }
  return `${lat.toFixed(6)},${lng.toFixed(6)}`;
}

const TRAVEL_MODE_OPTIONS = [
  { value: 'driving', label: '驾车' },
  { value: 'transit', label: '公交' },
  { value: 'walking', label: '步行' },
];

const DEFAULT_CENTER: [number, number] = [39.90923, 116.397428];

export default function ApplicantProfilePage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [mapModalOpen, setMapModalOpen] = useState(false);
  const [searchResults, setSearchResults] = useState<Array<{ name: string; address: string; location: string }>>([]);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [selectedPoi, setSelectedPoi] = useState<{ name: string; lng: number; lat: number } | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);

  useEffect(() => {
    const loadProfile = async () => {
      try {
        const profile = await getApplicantProfile();
        form.setFieldsValue({
          home_address: profile.home_address || '',
          home_lng: profile.home_lng,
          home_lat: profile.home_lat,
          default_travel_mode: profile.default_travel_mode || 'transit',
          interview_duration_min: profile.interview_duration_min ?? 60,
          min_gap_min: profile.min_gap_min ?? 120,
          max_daily_interviews: profile.max_daily_interviews ?? 3,
          workday_start: profile.workday_start || '09:00',
          workday_end: profile.workday_end || '18:00',
        });
      } catch {
        message.error('加载配置失败');
      } finally {
        setLoading(false);
      }
    };
    loadProfile();
  }, [form]);

  useEffect(() => {
    if (!mapModalOpen) return;

    const frame = requestAnimationFrame(() => {
      if (!mapContainerRef.current) return;
      if (mapInstanceRef.current) return;

      const map = L.map(mapContainerRef.current, {
        center: DEFAULT_CENTER,
        zoom: 12,
        zoomControl: true,
      });

      L.tileLayer('https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}', {
        attribution: '&copy; 高德地图',
        maxZoom: 18,
      }).addTo(map);

      map.on('click', async (e: L.LeafletMouseEvent) => {
        const { lat, lng } = e.latlng;
        try {
          const addr = await amapReverseGeocode(lng, lat);
          if (markerRef.current) {
            map.removeLayer(markerRef.current);
          }
          const marker = L.marker([lat, lng]).addTo(map);
          marker.bindPopup(addr);
          markerRef.current = marker;
          setSelectedPoi({ name: addr, lng, lat });
        } catch {
          message.error('获取地址失败');
        }
      });

      mapInstanceRef.current = map;

      // 自动定位到用户当前位置
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          async (pos) => {
            const lat = pos.coords.latitude;
            const lng = pos.coords.longitude;
            map.setView([lat, lng], 14);
            try {
              const addr = await amapReverseGeocode(lng, lat);
              if (markerRef.current) map.removeLayer(markerRef.current);
              const marker = L.marker([lat, lng]).addTo(map);
              marker.bindPopup(addr).openPopup();
              markerRef.current = marker;
              setSelectedPoi({ name: addr, lng, lat });
              setSearchKeyword(addr);
            } catch {}
          },
          () => {},
          { enableHighAccuracy: false, timeout: 15000, maximumAge: 120000 }
        );
      }
    });

    return () => {
      cancelAnimationFrame(frame);
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
      markerRef.current = null;
    };
  }, [mapModalOpen]);

  const handleOpenMapModal = useCallback(() => {
    setMapModalOpen(true);
    setSearchKeyword('');
    setSearchResults([]);
    setSelectedPoi(null);
  }, []);

  const handleSearch = useCallback(async (keyword: string) => {
    setSearchKeyword(keyword);
    if (!keyword.trim()) return;
    setSearchLoading(true);
    try {
      const pois = await amapPlaceSearch(keyword);
      setSearchResults(pois);
    } catch {
      message.error('搜索失败');
    } finally {
      setSearchLoading(false);
    }
  }, []);

  const handleSelectPoi = useCallback((poi: { name: string; lng: number; lat: number }) => {
    form.setFieldsValue({
      home_address: poi.name,
      home_lng: poi.lng,
      home_lat: poi.lat,
    });
    setMapModalOpen(false);
  }, [form]);

  const handleCloseModal = useCallback(() => {
    setMapModalOpen(false);
  }, []);

  const handleSave = useCallback(async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const result = await updateApplicantProfile(values);
      message.success(result?.message || '保存成功');
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'errorFields' in err) {
        return;
      }
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  }, [form]);

  const flyToPoi = useCallback((lat: number, lng: number, name: string) => {
    if (markerRef.current && mapInstanceRef.current) {
      mapInstanceRef.current.removeLayer(markerRef.current);
    }
    if (mapInstanceRef.current) {
      mapInstanceRef.current.setView([lat, lng], 15);
      const marker = L.marker([lat, lng]).addTo(mapInstanceRef.current);
      marker.bindPopup(name);
      markerRef.current = marker;
    }
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 300 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h2>求职者配置</h2>
        <p style={{ color: 'var(--admin-text-secondary)' }}>设置个人住址、交通方式和面试参数</p>
      </div>
      <Card>
        <Form
          form={form}
          layout="horizontal"
          labelCol={{ span: 6 }}
          wrapperCol={{ span: 14 }}
        >
          <Form.Item label="家庭住址" name="home_address">
            <Input.Search
              placeholder="请输入或选择地址"
              enterButton="选择地址"
              onSearch={() => handleOpenMapModal()}
            />
          </Form.Item>
          <Form.Item label="经度" name="home_lng" hidden>
            <InputNumber style={{ width: '100%' }} disabled />
          </Form.Item>
          <Form.Item label="纬度" name="home_lat" hidden>
            <InputNumber style={{ width: '100%' }} disabled />
          </Form.Item>
          <Form.Item label="默认交通方式" name="default_travel_mode">
            <Select options={TRAVEL_MODE_OPTIONS} />
          </Form.Item>
          <Form.Item label="面试时长 (分钟)" name="interview_duration_min">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="最小间隔 (分钟)" name="min_gap_min">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="每日最大面试数" name="max_daily_interviews">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="工作日起始时间" name="workday_start">
            <Input placeholder="例如 09:00" style={{ width: 120 }} />
          </Form.Item>
          <Form.Item label="工作日结束时间" name="workday_end">
            <Input placeholder="例如 18:00" style={{ width: 120 }} />
          </Form.Item>
          <Form.Item wrapperCol={{ offset: 6, span: 14 }}>
            <Button type="primary" onClick={handleSave} loading={saving}>
              保存
            </Button>
          </Form.Item>
        </Form>
      </Card>
      <Modal
        title="选择地址"
        open={mapModalOpen}
        onCancel={handleCloseModal}
        footer={selectedPoi ? (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--admin-text-secondary)', fontSize: 13 }}>已选: {selectedPoi.name}</span>
            <Button type="primary" onClick={() => handleSelectPoi(selectedPoi)}>确认选择</Button>
          </div>
        ) : null}
        width={1000}
        destroyOnClose
      >
        <div>
          <Input.Search
            placeholder="搜索地址..."
            value={searchKeyword}
            onChange={(e) => {
              setSearchKeyword(e.target.value);
              if (e.target.value.trim()) handleSearch(e.target.value);
            }}
            onSearch={handleSearch}
            style={{ marginBottom: 8 }}
            enterButton
          />
          <div style={{ position: 'relative' }}>
            {searchLoading && <div style={{ textAlign: 'center', padding: 8, color: 'var(--admin-text-secondary)' }}>搜索中...</div>}
            {!searchLoading && searchResults.length > 0 && (
              <div style={{
                maxHeight: 480,
                overflow: 'auto',
                border: '1px solid var(--admin-border)',
                borderRadius: 4,
                marginBottom: 8,
                background: 'var(--admin-bg, #0f1626)',
              }}>
                {searchResults.map((poi, idx) => {
                  const [lng, lat] = poi.location.split(',').map(Number);
                  return (
                    <div
                      key={`${poi.location}-${idx}`}
                      onClick={() => {
                        setSelectedPoi({ name: poi.name, lng, lat });
                        flyToPoi(lat, lng, poi.name);
                      }}
                      style={{
                        padding: '8px 12px',
                        cursor: 'pointer',
                        borderBottom: '1px solid var(--admin-border)',
                        color: 'var(--admin-text)',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--admin-accent-light, rgba(99,102,241,0.08))'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                    >
                      <div>{poi.name}</div>
                      {poi.address && <div style={{ fontSize: 12, color: 'var(--admin-text-secondary)' }}>{poi.address}</div>}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          <div ref={mapContainerRef} style={{ width: '100%', height: 350, borderRadius: 4, overflow: 'hidden' }} />
        </div>
      </Modal>
    </div>
  );
}
