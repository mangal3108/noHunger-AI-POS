import React, { useState, useEffect } from "react";
import { IoClose, IoPrintOutline } from "react-icons/io5";

const Bill = ({ items, onClose, isAdmin = false, customerDetails, orderDate, deliveryFee = 0, orderData, onTaxToggle, onApplyDiscount }) => {
    // We use data from orderData if available (persistent), effectively making this a "dumb" display component
    // If orderData is missing (preview mode), we fall back to local calc (rendering it useful for Cart preview if needed)

    // For Admin View, we MUST have orderData
    // For Admin View, we MUST have orderData

    // Calculate totals locally if orderData is missing (preview)
    // Formula: (Price - Disc) + Tax
    const calculateTotals = (itemsList) => {
        return itemsList.reduce((acc, item) => {
            const price = parseFloat(item.price);
            const qty = item.qty;
            const discountPercent = parseFloat(item.discount || 0);
            const taxPercent = parseFloat(item.tax || 0);

            const discountAmount = price * (discountPercent / 100);
            const priceAfterDiscount = price - discountAmount;
            const taxAmount = priceAfterDiscount * (taxPercent / 100);
            const finalPrice = priceAfterDiscount + taxAmount;

            acc.subtotal += price * qty;
            acc.discount += discountAmount * qty;
            acc.tax += taxAmount * qty;
            acc.total += finalPrice * qty;
            return acc;
        }, { subtotal: 0, discount: 0, tax: 0, total: 0 });
    };

    const totals = orderData
        ? {
            subtotal: orderData.subtotal,
            discount: orderData.discountAmount || 0, // Fallback if old order
            tax: orderData.taxAmount,
            total: orderData.totalAmount
        }
        : calculateTotals(items);

    const subtotal = totals.subtotal;
    const tax = totals.tax;
    const discountVal = totals.discount;
    // For old orders without discountAmount stored, we might show 0.
    // Ensure we don't double count delivery if it's already in totalAmount of orderData
    // If orderData exists, totalAmount includes everything. If not, we add delivery.
    const total = orderData ? orderData.totalAmount : (totals.total + deliveryFee);

    // Local state for loading tax toggle
    const [isUpdatingTax, setIsUpdatingTax] = useState(false);

    // Derived state for tax status
    const isTaxApplied = orderData?.isTaxApplied || false;

    const handleTaxToggle = async () => {
        if (!isAdmin || !onTaxToggle) return;
        setIsUpdatingTax(true);
        await onTaxToggle(!isTaxApplied);
        setIsUpdatingTax(false);
    };

    useEffect(() => {
        // Lock body scroll when modal is open
        document.body.style.overflow = 'hidden';
        return () => {
            document.body.style.overflow = 'auto';
        };
    }, []);

    const handlePrint = () => {
        window.print();
    };

    const formattedDate = orderDate ? new Date(orderDate).toLocaleDateString() : new Date().toLocaleDateString();
    const formattedTime = orderDate ? new Date(orderDate).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    return (
        <div
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex justify-center items-center z-50 print:bg-white print:static print:h-auto print:backdrop-blur-none p-4 transition-opacity duration-300"
        >
            <div
                onClick={(e) => e.stopPropagation()}
                className="bg-white w-full max-w-md rounded-xl shadow-2xl relative animate-fade-in-up print:shadow-none print:w-full print:p-0 font-mono text-sm border border-gray-200 max-h-[90vh] overflow-y-auto flex flex-col"
            >

                {/* Close Button (Hidden in Print) */}
                <button
                    onClick={onClose}
                    className="absolute top-2 right-2 md:-right-12 md:top-0 text-gray-500 md:text-white hover:text-red-500 md:hover:text-red-400 transition-colors print:hidden p-2"
                >
                    <IoClose size={32} />
                </button>

                {/* Receipt Content */}
                <div className="p-6 md:p-8 bg-white flex-1" id="receipt">
                    {/* Header */}
                    <div className="text-center mb-6">
                        <h2 className="text-2xl font-bold font-heading text-gray-900 tracking-wider">NoHunger</h2>
                        <p className="text-gray-500 mt-1 uppercase text-xs tracking-widest">Fine Dining & Takeaway</p>
                        <p className="text-gray-400 text-xs mt-1">123, Flavor Street, Food City</p>

                        <div className="border-b-2 border-dashed border-gray-300 my-4"></div>

                        <div className="flex justify-between text-xs text-gray-500 mb-2">
                            <div className="text-left">
                                <span className="block font-bold font-heading text-gray-700">Bill To:</span>
                                <span>{customerDetails?.name || "Guest"}</span>
                                {customerDetails?.phone && <span className="block">{customerDetails.phone}</span>}
                            </div>
                            <div className="text-right">
                                <span className="block">Date: {formattedDate}</span>
                                <span className="block">Time: {formattedTime}</span>
                                {orderData?.paymentMethod && (
                                    <span className="block font-bold text-blue-600 mt-1">{orderData.paymentMethod} Payment</span>
                                )}
                                {orderData?.transactionId && (
                                    <span className="block text-[10px] text-gray-400 font-mono">Txn: {orderData.transactionId}</span>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Items Table */}
                    <div className="mb-4">
                        <table className="w-full text-left">
                            <thead className="border-b border-dashed border-gray-300">
                                <tr className="text-xs text-gray-500 font-heading uppercase">
                                    <th className="py-2 font-normal">Item</th>
                                    <th className="py-2 text-center font-normal">Qty</th>
                                    <th className="py-2 text-right font-normal">Price</th>
                                    <th className="py-2 text-right font-normal">Discount</th>
                                    <th className="py-2 text-right font-normal">Tax</th>
                                    <th className="py-2 text-right font-normal">Amt</th>
                                </tr>
                            </thead>
                            <tbody className="text-gray-800">
                                {items.map((item) => {
                                    const price = parseFloat(item.price);
                                    // const qty = item.qty;
                                    const discountPercent = parseFloat(item.discount || 0);
                                    const taxPercent = parseFloat(item.tax || 0);

                                    // Check if tax should be applied (defaults to true for preview/home, respects orderData for admin)
                                    const shouldApplyTax = orderData ? orderData.isTaxApplied : true;

                                    const effectiveTaxPercent = shouldApplyTax ? taxPercent : 0;

                                    const discountAmount = price * (discountPercent / 100);
                                    const priceAfterDiscount = price - discountAmount;
                                    const taxAmount = priceAfterDiscount * (effectiveTaxPercent / 100);
                                    const finalPrice = priceAfterDiscount + taxAmount;

                                    return (
                                        <tr key={item.id || item.foodId} className="border-b border-gray-100 last:border-0 align-top">
                                            <td className="py-2 font-medium font-heading truncate max-w-[120px] capitalize">
                                                {item.name}
                                            </td>
                                            <td className="py-2 text-center">{item.qty}</td>
                                            <td className="py-2 text-right">₹{parseFloat(item.price).toFixed(2)}</td>
                                            <td className="py-2 text-right text-xs">
                                                {discountPercent > 0 && <div className="text-red-500">{discountPercent}%</div>}
                                            </td>
                                            <td className="py-2 text-right text-xs">
                                                {effectiveTaxPercent > 0 ? (
                                                    <div className="text-gray-600">{effectiveTaxPercent}%</div>
                                                ) : (
                                                    <div className="text-gray-400">0%</div>
                                                )}
                                            </td>
                                            <td className="py-2 text-right font-semibold">
                                                ₹{(finalPrice * item.qty).toFixed(2)}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>

                    {/* Separator */}
                    <div className="border-b-2 border-dashed border-gray-300 mb-4"></div>

                    {/* Summary */}
                    <div className="space-y-1 text-gray-600">
                        {/* 1. Total (Gross) */}
                        <div className="flex justify-between text-gray-600">
                            <span>Total</span>
                            <span>₹{subtotal.toFixed(2)}</span>
                        </div>

                        {/* 2. Discount (Item Discounts) */}
                        <div className="flex justify-between text-red-500">
                            <span>Discount</span>
                            <span>- ₹{discountVal.toFixed(2)}</span>
                        </div>

                        <div className="border-b border-dashed border-gray-300 my-1"></div>

                        {/* 3. Subtotal (Gross - Discount) */}
                        <div className="flex justify-between font-medium text-gray-700">
                            <span>Subtotal</span>
                            <span>₹{(subtotal - discountVal).toFixed(2)}</span>
                        </div>

                        {/* 4. Tax */}
                        <div className="flex justify-between text-gray-600">
                            <span>Tax</span>
                            <span>₹{tax.toFixed(2)}</span>
                        </div>

                        <div className="border-b border-dashed border-gray-300 my-1"></div>

                        {/* 5. Pay You Amount (Subtotal + Tax) */}
                        <div className="flex justify-between text-gray-800 font-bold">
                            <span>Pay You Amount</span>
                            <span>₹{((subtotal - discountVal) + tax).toFixed(2)}</span>
                        </div>

                        {/* 6. Admin Discount */}
                        {isAdmin && orderData ? (
                            <div className="py-2">
                                <div className="flex justify-between items-center mb-1">
                                    <span className="text-gray-800 font-medium">
                                        Admin Discount
                                        {orderData.adminDiscountPercentage > 0 && ` (${orderData.adminDiscountPercentage}%)`}
                                    </span>
                                    {orderData.adminDiscount > 0 && (
                                        <span className="text-red-500 font-medium">- ₹{parseFloat(orderData.adminDiscount).toFixed(2)}</span>
                                    )}
                                </div>
                                <div className="flex gap-2 items-center print:hidden">
                                    <input
                                        type="number"
                                        min="0"
                                        max="100"
                                        placeholder="%"
                                        className="w-16 flex-1 border border-gray-300 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-gray-800 outline-none"
                                        id="admin-discount-input"
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') {
                                                const val = parseFloat(e.target.value);
                                                if (!isNaN(val) && val >= 0 && val <= 100) {
                                                    if (onApplyDiscount) onApplyDiscount(val);
                                                    e.target.value = '';
                                                } else {
                                                    alert("Invalid percentage. Must be between 0 and 100.");
                                                }
                                            }
                                        }}
                                    />
                                    <button
                                        onClick={() => {
                                            const input = document.getElementById('admin-discount-input');
                                            const val = parseFloat(input.value);
                                            if (!isNaN(val) && val >= 0 && val <= 100) {
                                                if (onApplyDiscount) onApplyDiscount(val);
                                                input.value = '';
                                            } else {
                                                alert("Invalid percentage. Must be between 0 and 100.");
                                            }
                                        }}
                                        className="bg-gray-800 text-white text-[10px] uppercase font-bold px-3 py-1.5 rounded hover:bg-gray-900 transition-colors"
                                    >
                                        Apply %
                                    </button>
                                </div>
                            </div>
                        ) : (
                            orderData && orderData.adminDiscount > 0 && (
                                <div className="flex justify-between text-red-500">
                                    <span>
                                        Admin Discount
                                        {orderData.adminDiscountPercentage > 0 && ` (${orderData.adminDiscountPercentage}%)`}
                                    </span>
                                    <span>- ₹{parseFloat(orderData.adminDiscount).toFixed(2)}</span>
                                </div>
                            )
                        )}

                        <div className="border-b-2 border-dashed border-gray-300 my-2"></div>

                        {/* 7. Final Payable Amount (Pay You Amount - Admin Discount) */}
                        <div className="flex justify-between text-gray-900 font-bold font-heading text-lg">
                            <span>Final Payable Amount</span>
                            {/* logic: PayYouAmount - AdminDiscount. OrderData.totalAmount already has this if logic is correct. */}
                            {/* If local preview (orderData null), admin discount is 0 anyway. */}
                            <span>₹{orderData ? orderData.totalAmount.toFixed(2) : ((subtotal - discountVal) + tax).toFixed(2)}</span>
                        </div>
                    </div>
                    {/* Footer */}
                    <div className="mt-8 text-center space-y-2">
                        <p className="text-gray-800 font-semibold text-xs border-t border-b border-gray-200 py-2 inline-block px-4">THANK YOU FOR VISITING!</p>
                        <p className="text-[10px] text-gray-400">Please visit again</p>
                    </div>

                    {/* Actions (Hidden in Print) */}
                    <div className="bg-gray-50 p-4 border-t border-gray-100 flex gap-3 print:hidden rounded-b-xl sticky bottom-0 z-10 shrink-0">
                        <div className="flex items-center gap-2 flex-1">
                            {isAdmin && (
                                <>
                                    <input
                                        type="checkbox"
                                        id="tax-toggle"
                                        checked={isTaxApplied}
                                        onChange={handleTaxToggle}
                                        disabled={isUpdatingTax}
                                        className="w-4 h-4 text-gray-800 rounded focus:ring-gray-500 border-gray-300 disabled:opacity-50"
                                    />
                                    <label htmlFor="tax-toggle" className="text-xs text-gray-600 font-medium cursor-pointer select-none">
                                        {isUpdatingTax ? 'Updating...' : 'Apply Tax'}
                                    </label>
                                </>
                            )}
                        </div>

                        {isAdmin ? (
                            <button
                                onClick={handlePrint}
                                className="flex items-center gap-2 bg-gray-900 text-white px-4 py-2 rounded text-xs font-bold uppercase tracking-wider hover:bg-black transition-colors"
                            >
                                <IoPrintOutline size={16} /> Print
                            </button>
                        ) : (
                            <button
                                onClick={onClose}
                                className="flex items-center gap-2 bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-bold uppercase tracking-wider hover:bg-red-700 transition-colors shadow-sm"
                            >
                                Close
                            </button>
                        )}
                    </div>
                </div>

                <style>{`
                    @media print {
                        /* 1. Hide everything by default */
                        body * {
                            visibility: hidden;
                        }
                        /* 2. Show the receipt and its text */
                        #receipt, #receipt * {
                            visibility: visible;
                        }
                        /* 3. Pull the receipt out to the top left of the physical page */
                        #receipt {
                            position: absolute !important;
                            left: 0 !important;
                            top: 0 !important;
                            width: 100% !important;
                            background-color: white !important;
                            padding: 0 !important;
                            margin: 0 !important;
                        }
                        /* 4. Disable modal scroll locks and height limiters so it doesn't print a blank or cropped box */
                        html, body, #root, .fixed, .max-h-\\[90vh\\], .overflow-y-auto {
                            height: auto !important;
                            max-height: none !important;
                            overflow: visible !important;
                            position: static !important;
                        }
                        @page { 
                            size: auto;
                            margin: 0mm; /* This removes the browser's default header/footer (Vite + React text) */
                        }
                        /* Add some padding directly to the receipt instead of relying on page margins */
                        #receipt {
                            padding: 2cm !important;
                        }
                    }
                `}</style>
            </div>
        </div>
    );
};

export default Bill;
