# API 说明：创建订单接口

## 基本信息

- 服务名：order-service
- 模块名：order
- API 名称：createOrder
- 请求路径：`/api/v1/orders`
- 请求方法：`POST`

## 请求参数

请求体示例：

```json
{
  "userId": "u1001",
  "items": [
    {
      "skuId": "sku-001",
      "count": 2
    }
  ],
  "couponId": "cp-88",
  "addressId": "addr-003"
}
```

字段说明：

- `userId`：下单用户 ID
- `items`：商品项列表
- `skuId`：商品 SKU
- `count`：购买数量
- `couponId`：优惠券 ID，可为空
- `addressId`：收货地址 ID

## 返回结果

成功时返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "orderId": "ord-20260404001",
    "status": "CREATED"
  }
}
```

失败时可能返回：

```json
{
  "code": 50401,
  "message": "inventory service timeout"
}
```

## 常见问题

### 1. 为什么会返回库存服务超时

当库存服务 RT 抖动、线程池耗尽或 Redis 热 key 导致库存扣减链路变慢时，订单接口可能返回 `inventory service timeout`。

### 2. 是否应该重试

如果错误来自短暂性超时，可以做有限次数重试；如果是库存服务持续过载，应先降级或限流，盲目重试只会放大问题。
