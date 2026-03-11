import React, { useState } from 'react';
import usePagination from '../hooks/usePagination'; // Adjust path as needed
import { api } from '../helpers/api';
import { toast } from 'react-toastify';
import { IoArrowBack, IoSearch, IoWalletOutline, IoPeopleOutline } from 'react-icons/io5';
import { useNavigate } from 'react-router-dom';
import Bill from '../components/Bill'; // Adjust path
import ConfirmDialog from '../components/ConfirmDialog';

const AdminBill = () => {
    const navigate = useNavigate();
    const [fromDate, setFromDate] = useState('');
    const [toDate, setToDate] = useState('');
    const [viewBill, setViewBill] = useState(null); // Stores the order object to be viewed




    // Helper to build query string including date ranges
    const buildQuery = (params) => {
        let query = `?page=${params.page}&limit=${params.limit}`;
        if (fromDate) query += `&startDate=${fromDate}`;
        if (toDate) query += `&endDate=${toDate}`;
        return query;
    };

    let endpointParams = new URLSearchParams();
    if (fromDate) endpointParams.append('startDate', fromDate);
    if (toDate) endpointParams.append('endDate', toDate);
    const endpointStr = endpointParams.toString();
    const endpoint = '/orders' + (endpointStr ? `?${endpointStr}` : '');

    const {
        data: orders,
        extraData,
        loading,
        error,
        totalPages,
        page: currentPage,
        jumpToPage: handlePageChange,
        refresh: refreshData,
        setData,
        setPage, // Extract setPage to reset pagination on filter change
        limit,
        setLimit
    } = usePagination(endpoint, 10);

    const { totalIncome = 0, totalCustomers = 0 } = extraData || {};



    // Re-fetch when date changes. 
    // Note: usePagination dependencies should include selectedDate if we want auto-refetch, 
    // or we pass a key, or we manually trigger.
    // simpler: Pass url with query params directly.
    // Correction: usePagination hook implementation checks the URL? 
    // Let's assume usePagination might need a dependency array or we trigger it.
    // If usePagination doesn't support dyn dependency, we can just force update by changing the 1st arg key (if it works like SWR) 
    // or passing the query function.
    // Let's modify the usage: pass query builder to hook or pass full URL.
    // Assuming standard fetch, we might need a useEffect to call fetch when selectedDate changes in the hook, 
    // OR we just use a wrapper here. 
    // Let's try passing the Full URL string constructed dynamically? No, hook usually takes base.

    // Confirmation State
    const [confirmAction, setConfirmAction] = useState({
        isOpen: false,
        order: null,
        newStatus: null,
        title: "",
        message: ""
    });

    // Confirmation State for Discount
    const [confirmDiscount, setConfirmDiscount] = useState({
        isOpen: false,
        amount: 0
    });

    // Handle Status Update
    const [updatingStatus, setUpdatingStatus] = useState({});

    const initiateToggleStatus = (order) => {
        if (updatingStatus[order._id] || order.status === 1) return;

        const newStatus = order.status === 1 ? 2 : 1;
        setConfirmAction({
            isOpen: true,
            order: order,
            newStatus: newStatus,
            title: "Update Bill Status",
            message: `Are you sure you want to mark this bill as ${newStatus === 1 ? 'PAID' : 'UNPAID'}?`
        });
    };

    const performStatusToggle = async () => {
        const { order, newStatus } = confirmAction;
        if (!order) return;

        try {
            setUpdatingStatus(prev => ({ ...prev, [order._id]: true }));
            await api.put(`/orders/${order._id}/status`, { status: newStatus });

            setData(prevOrders =>
                prevOrders.map(o =>
                    o._id === order._id ? { ...o, status: newStatus } : o
                )
            );
            toast.success(`Order marked as ${newStatus === 1 ? 'Paid' : 'Unpaid'}`);
        } catch (err) {
            console.error(err);
            toast.error("Failed to update status");
        } finally {
            setUpdatingStatus(prev => {
                const newState = { ...prev };
                delete newState[order._id];
                return newState;
            });
            setConfirmAction({ ...confirmAction, isOpen: false });
        }
    };

    const initiateApplyDiscount = (amount) => {
        setConfirmDiscount({
            isOpen: true,
            amount: amount
        });
    };

    const performApplyDiscount = async () => {
        if (!viewBill) return;

        try {
            // Updated endpoint to match OrderRoutes and simple percentage logic
            const { data } = await api.put(`/orders/${viewBill._id}/discount`, {
                adminDiscountPercentage: confirmDiscount.amount
            });

            // Update local state
            setViewBill(data.order);
            setData(prevOrders =>
                prevOrders.map(o =>
                    o._id === viewBill._id ? data.order : o
                )
            );
            toast.success("Discount applied successfully");
            setConfirmDiscount({ ...confirmDiscount, isOpen: false });
        } catch (error) {
            console.error(error);
            toast.error(error.response?.data?.message || "Failed to apply discount");
        }
    };

    // Handle Tax Toggle (Passed to Bill Component)
    const handleTaxToggle = async (newTaxStatus) => {
        if (!viewBill) return;

        try {
            const { data } = await api.put(`/orders/${viewBill._id}/tax`, { isTaxApplied: newTaxStatus });

            // Update local state for the modal
            setViewBill(data.order);

            // Update list state
            setData(prevOrders =>
                prevOrders.map(o =>
                    o._id === viewBill._id ? data.order : o
                )
            );
            toast.success(`Tax ${newTaxStatus ? 'Enabled' : 'Disabled'}`);
        } catch (error) {
            console.error(error);
            toast.error("Failed to update tax status");
        }
    };

    // Handle Multi-Stage Bill Update
    const onUpdateBillDetails = async (billDetails) => {
        if (!viewBill) return;

        try {
            const { data } = await api.put(`/orders/${viewBill._id}/bill`, billDetails);

            // Update local state
            setViewBill(data.order);

            // Update list
            setData(prevOrders =>
                prevOrders.map(o =>
                    o._id === viewBill._id ? data.order : o
                )
            );
            toast.success("Bill updated successfully");
        } catch (error) {
            console.error(error);
            toast.error(error.response?.data?.message || "Failed to update bill");
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 p-6 md:p-10">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
                <div className="flex items-center gap-4 w-full md:w-auto">
                    <button
                        onClick={() => navigate('/admin/dashboard')}
                        className="p-2 bg-white rounded-lg shadow-sm hover:bg-gray-100 text-gray-600 transition-colors"
                    >
                        <IoArrowBack size={24} />
                    </button>
                    <h1 className="text-2xl font-bold text-gray-800">Bill Management</h1>
                </div>

                {/* Filters */}
                <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto bg-white p-2 rounded-lg shadow-sm border border-gray-200">
                    <span className="text-sm font-medium text-gray-500 pl-2">From:</span>
                    <input
                        type="date"
                        value={fromDate}
                        onChange={(e) => {
                            setFromDate(e.target.value);
                            setPage(1); // Reset to first page when filter changes
                        }}
                        className="outline-none text-gray-700 font-medium text-sm border-r border-gray-200 pr-2"
                    />
                    <span className="text-sm font-medium text-gray-500 pl-2">To:</span>
                    <input
                        type="date"
                        value={toDate}
                        onChange={(e) => {
                            setToDate(e.target.value);
                            setPage(1); // Reset to first page when filter changes
                        }}
                        className="outline-none text-gray-700 font-medium text-sm"
                    />
                    {/* Manual Refresh Button just in case user wants to force */}
                    <button onClick={refreshData} className="p-1 sm:ml-2 text-green-600 hover:bg-green-50 rounded">
                        <IoSearch size={20} />
                    </button>
                </div>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                {/* Total Income Card */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col items-center justify-center relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-green-50 rounded-bl-full -z-10 opacity-60"></div>
                    <div className="p-3 bg-green-100/50 text-green-600 rounded-2xl mb-4">
                        <IoWalletOutline size={32} />
                    </div>
                    <h3 className="text-gray-500 font-medium text-sm mb-1 uppercase tracking-wider">Total Income (Paid)</h3>
                    <p className="text-3xl font-bold text-gray-800">₹{totalIncome.toFixed(2)}</p>
                </div>

                {/* Total Customers Card */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col items-center justify-center relative overflow-hidden">
                    <div className="absolute top-0 left-0 w-32 h-32 bg-blue-50 rounded-br-full -z-10 opacity-60"></div>
                    <div className="p-3 bg-blue-100/50 text-blue-600 rounded-2xl mb-4">
                        <IoPeopleOutline size={32} />
                    </div>
                    <h3 className="text-gray-500 font-medium text-sm mb-1 uppercase tracking-wider">Total Customers</h3>
                    <p className="text-3xl font-bold text-gray-800">{totalCustomers}</p>
                </div>
            </div>

            {/* Table Card */}
            <div className="bg-white rounded-xl shadow-lg overflow-hidden border border-gray-100">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">

                        <thead>
                            <tr className="bg-gray-50 border-b border-gray-200 text-gray-500 text-xs font-semibold uppercase tracking-wider">
                                <th className="px-3 py-2 text-left">Order ID</th>
                                <th className="px-3 py-2 text-left">Date & Time</th>
                                <th className="px-3 py-2 text-left">User Name</th>
                                <th className="px-3 py-2 text-left">Phone</th>
                                <th className="px-3 py-2 text-left">Source</th>
                                <th className="px-3 py-2 text-left">Payment</th>
                                <th className="px-3 py-2 text-left">Txn ID</th>
                                <th className="px-3 py-2 text-left">Email</th>
                                <th className="px-3 py-2 text-right">Amount</th>
                                <th className="px-3 py-2 text-center">Action</th>
                                <th className="px-3 py-2 text-center">Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {loading ? (
                                <tr>
                                    <td colSpan="8" className="p-8 text-center text-gray-500">Loading orders...</td>
                                </tr>
                            ) : error ? (
                                <tr>
                                    <td colSpan="8" className="p-8 text-center text-red-500">{error}</td>
                                </tr>
                            ) : orders.length === 0 ? (
                                <tr>
                                    <td colSpan="8" className="p-8 text-center text-gray-400">No orders found.</td>
                                </tr>
                            ) : (
                                orders.map((order) => (
                                    <tr key={order._id} className="hover:bg-gray-50 transition-colors text-sm">
                                        <td className="px-3 py-2 text-gray-500 font-mono text-xs">
                                            #{order._id.slice(-6).toUpperCase()}
                                        </td>
                                        <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                                            <div className="flex flex-col">
                                                <span className="font-medium text-gray-700 text-xs">{new Date(order.createdAt).toLocaleDateString()}</span>
                                                <span className="text-[10px] text-gray-400">{new Date(order.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                            </div>
                                        </td>
                                        <td className="px-3 py-2 font-medium text-gray-800 whitespace-nowrap text-xs">{order.user?.name || "Unknown"}</td>
                                        <td className="px-3 py-2 text-gray-600 whitespace-nowrap text-xs">{order.user?.phone || "N/A"}</td>
                                        <td className="px-3 py-2 text-center text-xs">
                                            {order.source === 'chatbot' ? (
                                                <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-[10px] font-bold">Chatbot AI</span>
                                            ) : (
                                                <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-[10px] font-bold">Web User</span>
                                            )}
                                        </td>
                                        <td className="px-3 py-2 text-xs">
                                            <span className={`px-2 py-1 rounded text-[10px] font-bold ${order.paymentMethod ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'}`}>
                                                {order.paymentMethod || 'N/A'}
                                            </span>
                                        </td>
                                        <td className="px-3 py-2 text-xs font-mono text-gray-500" title={order.transactionId}>
                                            {order.transactionId ? order.transactionId.slice(-8) : 'N/A'}
                                        </td>
                                        <td className="px-3 py-2 text-gray-600 max-w-[150px] truncate text-xs" title={order.user?.email || ""}>{order.user?.email || "N/A"}</td>
                                        <td className="px-3 py-2 font-bold text-gray-800 text-right text-xs">₹{order.totalAmount.toFixed(2)}</td>

                                        {/* Bill Button */}
                                        <td className="px-3 py-2 text-center">
                                            <button
                                                onClick={() => setViewBill(order)}
                                                className="text-blue-600 hover:text-blue-800 font-medium text-xs underline decoration-1 underline-offset-2 transition-colors"
                                            >
                                                View
                                            </button>
                                        </td>

                                        {/* Paid Status Button */}
                                        <td className="px-3 py-2 text-center">
                                            <button
                                                onClick={() => initiateToggleStatus(order)}
                                                disabled={updatingStatus[order._id] || order.status === 1}
                                                title={order.status === 1 ? "Paid bills cannot be modified" : "Click to mark as Paid"}
                                                className={`
                                                    px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider transition-all shadow-sm border
                                                    ${updatingStatus[order._id]
                                                        ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-wait'
                                                        : order.status === 1
                                                            ? 'bg-green-50 text-green-600 border-green-200 cursor-not-allowed'
                                                            : 'bg-white text-red-600 border-red-200 hover:bg-red-50 cursor-pointer'}
                                                `}
                                            >
                                                {updatingStatus[order._id] ? '...' : (order.status === 1 ? 'Paid' : 'Unpaid')}
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Pagination */}
                {!loading && orders.length > 0 && (
                    <div className="flex flex-col md:flex-row justify-between items-center p-6 border-t border-gray-100 bg-gray-50/30 gap-4">
                        <div className="flex items-center gap-4">
                            <span className="text-sm text-gray-500">
                                Showing page <span className="font-semibold text-gray-700">{currentPage}</span> of <span className="font-semibold text-gray-700">{totalPages}</span>
                            </span>
                            <div className="flex items-center gap-2">
                                <label htmlFor="limit" className="text-sm text-gray-500">Rows per page:</label>
                                <select
                                    id="limit"
                                    value={limit}
                                    onChange={(e) => {
                                        setLimit(Number(e.target.value));
                                        setPage(1); // Reset to first page on limit change
                                    }}
                                    className="border border-gray-200 rounded-lg text-sm text-gray-700 p-1 outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                                >
                                    <option value={10}>10</option>
                                    <option value={25}>25</option>
                                    <option value={50}>50</option>
                                    <option value={75}>75</option>
                                    <option value={100}>100</option>
                                </select>
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            <button
                                disabled={currentPage === 1}
                                onClick={() => handlePageChange(currentPage - 1)}
                                className="px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 disabled:opacity-40 hover:bg-gray-50 transition shadow-sm"
                            >
                                Previous
                            </button>
                            <button
                                disabled={currentPage === totalPages}
                                onClick={() => handlePageChange(currentPage + 1)}
                                className="px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 disabled:opacity-40 hover:bg-gray-50 transition shadow-sm"
                            >
                                Next
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* Bill Modal (Admin Mode) */}
            {viewBill && (
                <Bill
                    items={viewBill.items}
                    customerDetails={viewBill.user}
                    orderDate={viewBill.createdAt}
                    deliveryFee={viewBill.deliveryFee !== undefined ? viewBill.deliveryFee : 0} // Use stored delivery fee or default to 0
                    onClose={() => setViewBill(null)}
                    isAdmin={true}
                    orderData={viewBill} // Pass full order object
                    onTaxToggle={handleTaxToggle}
                    onApplyDiscount={initiateApplyDiscount}
                />
            )}

            <ConfirmDialog
                isOpen={confirmAction.isOpen}
                onClose={() => setConfirmAction({ ...confirmAction, isOpen: false })}
                onConfirm={performStatusToggle}
                title={confirmAction.title}
                message={confirmAction.message}
                isDestructive={confirmAction.newStatus === 2} // Unpaid is destructive-ish? Or maybe Paid is definitive. Let's make it standard (blue). Actually user said "modern, styled". Blue is fine.
                confirmText="Yes, Change Status"
            />

            <ConfirmDialog
                isOpen={confirmDiscount.isOpen}
                onClose={() => setConfirmDiscount({ ...confirmDiscount, isOpen: false })}
                onConfirm={performApplyDiscount}
                title="Apply Admin Discount"
                message={`Are you sure you want to apply a ${confirmDiscount.amount}% discount? This will recalculate the tax.`}
                isDestructive={true}
                confirmText="Apply Discount"
            />


        </div>
    );
};

export default AdminBill;
