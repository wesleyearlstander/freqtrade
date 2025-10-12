#!/bin/bash
echo "=== 5-Year Hyperopt Progress Monitor ==="
echo "Time: $(date)"
echo ""

# Check if hyperopt is still running
if pgrep -f "freqtrade hyperopt" > /dev/null; then
    echo "✅ Hyperopt Status: RUNNING"
    echo "📊 Process Info:"
    ps aux | grep "freqtrade hyperopt" | grep -v grep | awk "{print \"   PID: \" \$2 \", CPU: \" \$3 \"%, Memory: \" \$4 \"%\"}"
else
    echo "❌ Hyperopt Status: STOPPED"
fi

echo ""
echo "📁 Latest Results Files:"
ls -lt user_data/hyperopt_results/*.fthypt 2>/dev/null | head -2 | while read line; do
    echo "   $line"
done

echo ""
echo "💾 Data Files:"
ls -lh user_data/hyperopt_results/hyperopt_tickerdata.pkl 2>/dev/null || echo "   No ticker data file found"

echo ""
echo "=== End Monitor ===" 

