const express = require('express');
const router = express.Router();
const orderController = require('../controllers/orderController');
const { protect, admin } = require('../middleware/authMiddleware');

router.post('/', orderController.createOrder); // Public route for users to place orders
router.get('/unique-users', protect, admin, orderController.getUniqueUsers); // Admin only - must be before /:id to not be treated as an ID
router.get('/', protect, admin, orderController.getAllOrders); // Admin only
router.put('/:id/status', protect, admin, orderController.updateOrderStatus); // Admin only
router.put('/confirm-payment/:id', orderController.confirmPayment);
router.put('/:id/tax', protect, admin, orderController.toggleOrderTax); // Admin only
router.put('/:id/discount', protect, admin, orderController.applyAdminDiscount); // Legacy support or remove
router.put('/:id/bill', protect, admin, orderController.updateOrderBill); // New Multi-stage update

module.exports = router;
