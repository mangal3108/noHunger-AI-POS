const Order = require('../models/Order');
const paginate = require('../utils/pagination');

// Create a new order
exports.createOrder = async (req, res) => {
    try {
        const { user, items, source } = req.body;

        // Calculate totals based on items
        let subtotal = 0;
        let totalDiscount = 0;
        let totalTax = 0;

        const processedItems = items.map(item => {
            const price = parseFloat(item.price);
            const qty = parseInt(item.qty);
            const discountPercent = parseFloat(item.discount || 0);
            const taxPercent = parseFloat(item.tax || 0);

            const discountAmount = price * (discountPercent / 100);
            const priceAfterDiscount = price - discountAmount;
            const taxAmountItem = priceAfterDiscount * (taxPercent / 100);
            // const finalPrice = priceAfterDiscount + taxAmountItem; // Per item final price

            subtotal += price * qty;
            totalDiscount += discountAmount * qty;
            totalTax += taxAmountItem * qty;

            return {
                ...item,
                discount: discountPercent,
                tax: taxPercent
            };
        });

        // Fixed delivery fee for now
        const deliveryFee = 0; // 20;

        const totalAmount = (subtotal - totalDiscount) + totalTax + deliveryFee;

        const newOrder = new Order({
            user,
            items: processedItems,
            subtotal,
            discountAmount: totalDiscount,
            taxAmount: totalTax,
            deliveryFee,
            isTaxApplied: totalTax > 0, // Set flag if tax exists
            totalAmount,
            source: source || 'user'
        });

        await newOrder.save();
        res.status(201).json({ message: "Order placed successfully", order: newOrder });
    } catch (error) {
        console.error("Create Order Error:", error);
        res.status(500).json({ message: error.message });
    }
};

// Get all orders (with pagination and optional date filter)
exports.getAllOrders = async (req, res) => {
    try {
        const { skip, limit, getMetadata } = paginate(req.query);
        const { date, startDate, endDate } = req.query;

        let query = {};

        // Date filter (matches the entire day)
        if (date || startDate || endDate) {
            query.createdAt = {};
            if (date) {
                const sDate = new Date(date);
                sDate.setHours(0, 0, 0, 0);
                const eDate = new Date(date);
                eDate.setHours(23, 59, 59, 999);
                query.createdAt = {
                    $gte: sDate,
                    $lte: eDate
                };
            } else {
                if (startDate) {
                    const sDate = new Date(startDate);
                    sDate.setHours(0, 0, 0, 0);
                    query.createdAt.$gte = sDate;
                }
                if (endDate) {
                    const eDate = new Date(endDate);
                    eDate.setHours(23, 59, 59, 999);
                    query.createdAt.$lte = eDate;
                }
            }
        }

        const orders = await Order.find(query)
            .sort({ createdAt: -1 })
            .skip(skip)
            .limit(limit);

        const total = await Order.countDocuments(query);

        // Calculate summary statistics
        const [stats] = await Order.aggregate([
            { $match: query },
            {
                $group: {
                    _id: null,
                    totalIncome: {
                        $sum: { $cond: [{ $eq: ["$status", 1] }, "$totalAmount", 0] }
                    },
                    uniquePhones: { $addToSet: "$user.phone" }
                }
            },
            {
                $project: {
                    totalIncome: 1,
                    totalCustomers: { $size: "$uniquePhones" }
                }
            }
        ]);

        const totalIncome = stats ? stats.totalIncome : 0;
        const totalCustomers = stats ? stats.totalCustomers : 0;

        res.status(200).json({
            orders,
            totalIncome,
            totalCustomers,
            ...getMetadata(total)
        });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

// Toggle Tax for an Order (Admin Only)
exports.toggleOrderTax = async (req, res) => {
    try {
        const { id } = req.params;
        const { isTaxApplied } = req.body; // true or false

        const order = await Order.findById(id);
        if (!order) {
            return res.status(404).json({ message: "Order not found" });
        }

        let newTaxAmount = 0;

        if (isTaxApplied) {
            // Calculate Base Tax (Tax on items after item discounts)
            // This is the full tax amount based on item tax %
            newTaxAmount = order.items.reduce((acc, item) => {
                const price = parseFloat(item.price);
                const qty = parseInt(item.qty);
                const discountPercent = parseFloat(item.discount || 0);
                const taxPercent = parseFloat(item.tax || 0);

                const discountAmount = price * (discountPercent / 100);
                const priceAfterDiscount = price - discountAmount;
                const itemTaxAmount = priceAfterDiscount * (taxPercent / 100);

                return acc + (itemTaxAmount * qty);
            }, 0);
        }

        // Order Total (Gross - Item Disc)
        const orderTotal = order.subtotal - order.discountAmount;

        // Calculate "Pay You Amount" (Amount before Admin Discount)
        // Pay You Amount = (Subtotal - Item Discount) + Tax + Delivery
        const payYouAmount = orderTotal + newTaxAmount + (order.deliveryFee || 0);

        // Recalculate Admin Discount Amount based on new Pay You Amount
        // Admin Discount is a percentage of Pay You Amount
        const adminDiscountPercentage = order.adminDiscountPercentage || 0;
        const adminDiscountAmount = payYouAmount * (adminDiscountPercentage / 100);

        // Final Total Amount = Pay You Amount - Admin Discount
        const newTotalAmount = payYouAmount - adminDiscountAmount;

        // Update fields
        order.isTaxApplied = isTaxApplied;
        order.taxAmount = newTaxAmount;
        order.adminDiscount = adminDiscountAmount; // Update amount as it depends on Pay You Amount
        order.totalAmount = newTotalAmount;

        await order.save();

        res.status(200).json({ message: `Tax ${isTaxApplied ? 'enabled' : 'disabled'}`, order });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

// Apply Admin Discount
exports.applyAdminDiscount = async (req, res) => {
    try {
        const { id } = req.params;
        const { adminDiscountPercentage } = req.body; // Should be a number 0-100

        const order = await Order.findById(id);
        if (!order) {
            return res.status(404).json({ message: "Order not found" });
        }

        // Validate percentage
        if (adminDiscountPercentage < 0 || adminDiscountPercentage > 100) {
            return res.status(400).json({ message: "Discount percentage must be between 0 and 100" });
        }

        // 1. Calculate Order Total (Gross - Item Discounts)
        const orderTotal = order.subtotal - order.discountAmount;

        // 2. Calculate Tax (Existing Tax Amount logic - remains same as it only depends on items)
        // However, we need to ensure we have the correct tax amount. 
        // If tax is applied, we re-calculate it to satisfy "Tax on Subtotal" rule strictly or trust stored value.
        // Let's recalculate to be safe and consistent with toggleOrderTax.
        let currentTaxAmount = 0;
        if (order.isTaxApplied) {
            currentTaxAmount = order.items.reduce((acc, item) => {
                const price = parseFloat(item.price);
                const qty = parseInt(item.qty);
                const discountPercent = parseFloat(item.discount || 0);
                const taxPercent = parseFloat(item.tax || 0);

                const discountAmount = price * (discountPercent / 100);
                const priceAfterDiscount = price - discountAmount;
                const itemTaxAmount = priceAfterDiscount * (taxPercent / 100);

                return acc + (itemTaxAmount * qty);
            }, 0);
        } else {
            currentTaxAmount = 0;
        }

        // 3. Calculate Pay You Amount
        // Pay You Amount = (Order Total) + Tax + Delivery
        const payYouAmount = orderTotal + currentTaxAmount + (order.deliveryFee || 0);

        // 4. Calculate Admin Discount Amount
        // Admin Discount = Pay You Amount * (Percentage / 100)
        const adminDiscountAmount = payYouAmount * (adminDiscountPercentage / 100);

        // 5. Final Total
        // Total = Pay You Amount - Admin Discount
        const newTotalAmount = payYouAmount - adminDiscountAmount;

        // Save
        order.adminDiscountPercentage = adminDiscountPercentage;
        order.adminDiscount = adminDiscountAmount;
        order.taxAmount = currentTaxAmount; // Ensure tax is correct (should be same unless we had the old reduction logic applied)
        order.totalAmount = newTotalAmount;

        await order.save();

        res.status(200).json({ message: "Admin discount applied", order });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

// Update order status (Paid/Unpaid)
exports.updateOrderStatus = async (req, res) => {
    try {
        const { id } = req.params;
        const { status } = req.body;

        const order = await Order.findByIdAndUpdate(
            id,
            { status },
            { new: true }
        );

        if (!order) {
            return res.status(404).json({ message: "Order not found" });
        }

        res.status(200).json({ message: "Order status updated", order });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

// Update Multi-Stage Bill Details (Admin Only)
exports.updateOrderBill = async (req, res) => {
    try {
        const { id } = req.params;
        const { defaultDiscountPercentage, taxPercentage, extraDiscountPercentage } = req.body;

        const order = await Order.findById(id);
        if (!order) {
            return res.status(404).json({ message: "Order not found" });
        }

        // 1. Gross Total (Sum of Item Prices * Qty, minus Item Discounts) - base for calculation
        // Ensure values are numbers to prevent NaN
        const subtotal = order.subtotal || 0;
        const discountAmount = order.discountAmount || 0;
        const orderTotal = subtotal - discountAmount;

        // 2. Default Discount
        const defDiscPercent = parseFloat(defaultDiscountPercentage || 0);
        const defDiscAmount = orderTotal * (defDiscPercent / 100);
        const amountAfterDiscount = orderTotal - defDiscAmount;

        // 3. Tax
        // "Calculate tax on the discounted amount (after default discount)."
        const taxPercent = parseFloat(taxPercentage || 0);
        const taxAmount = amountAfterDiscount * (taxPercent / 100);
        const amountWithTax = amountAfterDiscount + taxAmount;

        // 4. Extra Admin Discount
        // "Apply on Amount With Tax."
        const extraDiscPercent = parseFloat(extraDiscountPercentage || 0);
        // "Result -> Final Payable Amount ('You Pay')"
        // Formula: Amount With Tax - (Amount With Tax * Extra%)?
        // Yes: "Admin Extra Discount (%) ... Apply on Amount With Tax"
        const extraDiscAmount = amountWithTax * (extraDiscPercent / 100);
        const finalPayable = amountWithTax - extraDiscAmount;

        // Update Fields
        order.defaultDiscountPercentage = defDiscPercent;
        order.defaultDiscountAmount = defDiscAmount;
        order.amountAfterDiscount = amountAfterDiscount;

        order.taxPercentage = taxPercent;
        order.taxAmount = taxAmount;
        order.amountWithTax = amountWithTax;

        order.extraDiscountPercentage = extraDiscPercent;
        order.extraDiscountAmount = extraDiscAmount;

        order.totalAmount = finalPayable + (order.deliveryFee || 0);

        await order.save();

        res.status(200).json({ message: "Bill updated successfully", order });

    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

// Get Unique Users Grouped by Phone (with Pagination)
exports.getUniqueUsers = async (req, res) => {
    try {
        const { skip, limit, getMetadata, page } = paginate(req.query);

        // Use facet to get both total count and paginated results in one query
        const aggregationResult = await Order.aggregate([
            {
                $group: {
                    _id: "$user.phone",
                    name: { $first: "$user.name" },
                    email: { $first: "$user.email" },
                    phone: { $first: "$user.phone" },
                    totalOrders: { $sum: 1 },
                    lastOrderDate: { $max: "$createdAt" }
                }
            },
            {
                $facet: {
                    metadata: [{ $count: "totalCount" }],
                    data: [
                        { $sort: { lastOrderDate: -1 } }, // Sort by recent activity
                        { $skip: skip },
                        { $limit: limit }
                    ]
                }
            }
        ]);

        const totalCount = aggregationResult[0].metadata.length > 0
            ? aggregationResult[0].metadata[0].totalCount
            : 0;
        const uniqueUsers = aggregationResult[0].data;

        // Use our getMetadata utility. The paginate util needs total documents.
        const paginationMeta = getMetadata(totalCount);

        res.status(200).json({
            users: uniqueUsers,
            ...paginationMeta
        });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

// Confirm Payment (Set status to Paid and save transaction info)
exports.confirmPayment = async (req, res) => {
    try {
        const { id } = req.params;
        const { paymentMethod, transactionId } = req.body;

        const order = await Order.findById(id);
        if (!order) {
            return res.status(404).json({ message: "Order not found" });
        }

        order.status = 1; // Mark as Paid
        order.paymentMethod = paymentMethod;
        order.transactionId = transactionId;
        order.paidAt = new Date();

        await order.save();
        res.status(200).json({ message: "Payment confirmed successfully", order });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

