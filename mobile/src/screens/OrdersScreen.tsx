import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text, View } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  VideoOrder,
  getOrders,
  orderAction,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Loading, Screen, Title } from '../components/ui';

type OrderActionName = 'pay' | 'render' | 'review' | 'approve' | 'deliver' | 'cancel' | 'refund';

const NEXT_ACTION: Record<string, { label: string; action: OrderActionName } | null> = {
  pending_payment: { label: 'Mark paid', action: 'pay' },
  queued: { label: 'Render', action: 'render' },
  rendering: { label: 'Check done → review', action: 'review' },
  awaiting_review: { label: 'Approve & deliver', action: 'deliver' },
  delivered: null,
  cancelled: { label: 'Mark refunded', action: 'refund' },
  refunded: null,
};

export default function OrdersScreen() {
  const { settings } = useSettings();
  const [orders, setOrders] = useState<VideoOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getOrders(settings);
      setOrders(res.orders);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);

  const act = async (id: number, action: OrderActionName) => {
    setBusyId(id);
    setError(null);
    try {
      await orderAction(settings, id, action);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <Title>Custom orders ({orders.length})</Title>
      <ErrorText message={error} />
      <Dim>
        Fan-paid custom videos. You review the finished video before
        anything is delivered — nothing goes out without your eyes on it.
      </Dim>
      <FlatList
        data={orders}
        keyExtractor={(o) => String(o.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={<Dim>No orders yet.</Dim>}
        renderItem={({ item }) => {
          const next = NEXT_ACTION[item.status];
          const cancellable = item.status !== 'delivered' && item.status !== 'cancelled' && item.status !== 'refunded';
          return (
            <Card>
              <Text style={{ color: C.text, fontWeight: '600' }}>
                #{item.id} · {item.scene_name}
              </Text>
              <Text style={{ color: C.dim, fontSize: 12, marginTop: 4 }}>
                {item.fan_handle} · {item.status} · {item.price_label} {item.price}
              </Text>
              {item.delivery_note ? (
                <Text style={{ color: C.dim, fontSize: 12 }}>{item.delivery_note}</Text>
              ) : null}
              <View style={{ flexDirection: 'row', marginTop: 8 }}>
                {next ? (
                  <Btn label={next.label} onPress={() => act(item.id, next.action)} disabled={busyId === item.id} />
                ) : null}
                {next && cancellable ? <View style={{ width: 8 }} /> : null}
                {cancellable ? (
                  <Btn label="Cancel" danger onPress={() => act(item.id, 'cancel')} disabled={busyId === item.id} />
                ) : null}
              </View>
            </Card>
          );
        }}
      />
    </Screen>
  );
}
