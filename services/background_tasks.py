import asyncio
import logging
from datetime import datetime
from typing import List

from models.order import OrderDTO, OrderStatus
from models.reservedStock import ReservedStockDTO
from repositories.order import OrderRepository
from repositories.reservedStock import ReservedStockRepository
from services.order import OrderService
from services.notification import NotificationService
import config

logger = logging.getLogger(__name__)


class BackgroundTaskService:
    @staticmethod
    async def process_expired_orders() -> None:
        """
        Process expired orders and handle cleanup
        """
        try:
            expired_orders = await OrderRepository.get_expired_orders()
            
            if not expired_orders:
                logger.info("No expired orders found")
                return
            
            logger.info(f"Processing {len(expired_orders)} expired orders")
            
            for order in expired_orders:
                try:
                    await OrderService.expire_order(order.id)
                    logger.info(f"Expired order {order.id} for user {order.user_id}")
                except Exception as e:
                    logger.error(f"Failed to expire order {order.id}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error processing expired orders: {str(e)}")
    
    @staticmethod
    async def cleanup_expired_reservations() -> None:
        """
        Clean up expired stock reservations that may have been left behind
        """
        try:
            expired_reservations = await ReservedStockRepository.get_expired_reservations()
            
            if not expired_reservations:
                logger.info("No expired reservations found")
                return
            
            logger.info(f"Cleaning up {len(expired_reservations)} expired reservations")
            
            # Group by order_id for batch cleanup
            order_ids = list(set([res.order_id for res in expired_reservations]))
            
            for order_id in order_ids:
                try:
                    await ReservedStockRepository.release_by_order_id(order_id)
                    logger.info(f"Released expired reservations for order {order_id}")
                except Exception as e:
                    logger.error(f"Failed to release reservations for order {order_id}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up expired reservations: {str(e)}")
    
    @staticmethod
    async def monitor_order_timeouts() -> None:
        """
        Monitor order timeouts and send warnings
        """
        try:
            # Get orders that are close to expiring (5 minutes remaining)
            current_time = datetime.now()
            
            # This would require a custom query to get orders expiring soon
            # For now, we'll focus on processing already expired orders
            logger.info("Order timeout monitoring completed")
            
        except Exception as e:
            logger.error(f"Error monitoring order timeouts: {str(e)}")

    @staticmethod
    async def run_background_tasks() -> None:
        """Run one cycle of background tasks with error isolation."""
        try:
            await BackgroundTaskService.process_expired_orders()
            await BackgroundTaskService.cleanup_expired_reservations()
            await BackgroundTaskService.monitor_order_timeouts()
        except Exception as e:
            logger.error(f"Background task execution error: {str(e)}")

    @staticmethod
    async def schedule_cleanup_tasks() -> None:
        """
        Schedule and run all cleanup tasks
        """
        interval_seconds = getattr(config, 'BACKGROUND_TASK_INTERVAL_SECONDS', 60)
        
        logger.info(f"Starting background task scheduler with {interval_seconds}s interval")
        
        while True:
            try:
                logger.info("Running background cleanup tasks")
                
                # Run all cleanup tasks
                await BackgroundTaskService.process_expired_orders()
                await BackgroundTaskService.cleanup_expired_reservations()
                await BackgroundTaskService.monitor_order_timeouts()
                
                logger.info("Background cleanup tasks completed")
                
                # Wait for next interval
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in background task scheduler: {str(e)}")
                # Continue running even if there's an error
                await asyncio.sleep(interval_seconds)
    
    @staticmethod
    async def run_single_cleanup() -> dict:
        """
        Run a single cleanup cycle and return results (useful for admin commands)
        """
        results = {
            'expired_orders': 0,
            'cleaned_reservations': 0,
            'errors': []
        }
        
        try:
            # Process expired orders
            expired_orders = await OrderRepository.get_expired_orders()
            for order in expired_orders:
                try:
                    await OrderService.expire_order(order.id)
                    results['expired_orders'] += 1
                except Exception as e:
                    results['errors'].append(f"Order {order.id}: {str(e)}")
            
            # Clean up reservations
            expired_reservations = await ReservedStockRepository.get_expired_reservations()
            order_ids = list(set([res.order_id for res in expired_reservations]))
            
            for order_id in order_ids:
                try:
                    await ReservedStockRepository.release_by_order_id(order_id)
                    results['cleaned_reservations'] += 1
                except Exception as e:
                    results['errors'].append(f"Reservations {order_id}: {str(e)}")
            
        except Exception as e:
            results['errors'].append(f"General error: {str(e)}")
        
        return results