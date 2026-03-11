import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { api } from '../helpers/api';
import { toast } from 'react-toastify';
import { FaCheckCircle, FaCreditCard, FaMobileAlt, FaUniversity, FaWallet } from 'react-icons/fa';

const Payment = () => {
    const { orderId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const queryParams = new URLSearchParams(location.search);
    const amount = queryParams.get('amount');
    const methodParam = queryParams.get('method')?.toUpperCase();
    const [selectedMethod, setSelectedMethod] = useState(methodParam || '');
    const [isProcessing, setIsProcessing] = useState(false);
    const [showSuccess, setShowSuccess] = useState(false);

    const paymentMethods = [
        { id: 'UPI', name: 'UPI (GPay, PhonePe)', icon: <FaMobileAlt className="text-purple-600" /> },
        { id: 'CARD', name: 'Credit / Debit Card', icon: <FaCreditCard className="text-blue-600" /> },
        { id: 'NETBANKING', name: 'Net Banking', icon: <FaUniversity className="text-green-600" /> },
        { id: 'WALLET', name: 'Wallets', icon: <FaWallet className="text-orange-600" /> }
    ];

    const handlePayment = async () => {
        if (!selectedMethod) {
            toast.error("Please select a payment method");
            return;
        }

        setIsProcessing(true);
        try {
            // Mock transaction details
            const transactionId = 'TXN_' + Math.random().toString(36).substr(2, 9).toUpperCase();

            // Call backend to confirm payment
            await api.put(`/orders/confirm-payment/${orderId}`, {
                paymentMethod: selectedMethod,
                transactionId: transactionId
            });

            setShowSuccess(true);
        } catch (error) {
            console.error(error);
            toast.error("Payment failed. Please try again.");
        } finally {
            setIsProcessing(false);
        }
    };

    if (showSuccess) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-md w-full text-center space-y-6 transform animate-bounce-short">
                    <div className="flex justify-center">
                        <FaCheckCircle className="text-green-500 text-7xl animate-pulse" />
                    </div>
                    <div className="space-y-2">
                        <h2 className="text-3xl font-bold text-gray-800">Payment Successful!</h2>
                        <p className="text-gray-500">Your order has been placed and paid.</p>
                    </div>
                    <div className="bg-green-50 rounded-2xl p-4 border border-green-100">
                        <p className="text-sm text-green-700 font-semibold mb-1">Order ID</p>
                        <p className="text-xl font-mono font-bold text-green-800">{orderId}</p>
                    </div>
                    <button
                        onClick={() => navigate('/')}
                        className="w-full py-4 bg-green-600 hover:bg-green-700 text-white rounded-xl font-bold transition-all shadow-lg hover:shadow-green-200"
                    >
                        Back to Home
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-3xl shadow-2xl overflow-hidden max-w-lg w-full flex flex-col">
                <div className="bg-gradient-to-r from-green-600 to-emerald-500 p-8 text-white relative">
                    <h1 className="text-2xl font-bold">Secure Checkout</h1>
                    <p className="opacity-90">Please complete your payment</p>
                    <div className="absolute top-8 right-8 text-right">
                        <p className="text-sm opacity-80 mb-0">Total Amount</p>
                        <p className="text-3xl font-bold">₹{amount || '0.00'}</p>
                    </div>
                </div>

                <div className="p-8 space-y-8">
                    <div className="space-y-4">
                        <h3 className="text-lg font-bold text-gray-700 flex items-center gap-2">
                            <span className="w-1 h-4 bg-green-500 rounded-full"></span>
                            Select Payment Method
                        </h3>
                        <div className="grid grid-cols-1 gap-3">
                            {paymentMethods.map((method) => (
                                <div
                                    key={method.id}
                                    onClick={() => setSelectedMethod(method.id)}
                                    className={`
                                        flex items-center gap-4 p-4 rounded-2xl border-2 cursor-pointer transition-all
                                        ${selectedMethod === method.id
                                            ? 'border-green-500 bg-green-50 shadow-md scale-102'
                                            : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50'}
                                    `}
                                >
                                    <div className="w-12 h-12 rounded-xl bg-white shadow-sm flex items-center justify-center text-2xl">
                                        {method.icon}
                                    </div>
                                    <span className="font-semibold text-gray-700">{method.name}</span>
                                    <div className={`ml-auto w-6 h-6 rounded-full border-2 flex items-center justify-center ${selectedMethod === method.id ? 'border-green-500 bg-green-500' : 'border-gray-300'}`}>
                                        {selectedMethod === method.id && <div className="w-2 h-2 bg-white rounded-full"></div>}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    <button
                        onClick={handlePayment}
                        disabled={isProcessing}
                        className={`
                            w-full py-5 rounded-2xl font-bold text-lg text-white transition-all shadow-xl
                            ${isProcessing
                                ? 'bg-gray-400 cursor-not-allowed'
                                : 'bg-green-600 hover:bg-green-700 active:scale-95 shadow-green-100'}
                        `}
                    >
                        {isProcessing ? 'Processing...' : `Pay ₹${amount || '0.00'}`}
                    </button>

                    <p className="text-center text-xs text-gray-400">
                        🔒 Secure encrypted payment. Your details are safe.
                    </p>
                </div>
            </div>

            <style jsx>{`
                .scale-102 { transform: scale(1.02); }
                @keyframes bounce-short {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-10px); }
                }
                .animate-bounce-short {
                    animation: bounce-short 0.5s ease-in-out;
                }
            `}</style>
        </div>
    );
};

export default Payment;
